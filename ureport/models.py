# -*- coding: utf-8 -*-
from django.db import models
from poll.models import Poll, LocationResponseForm, STARTSWITH_PATTERN_TEMPLATE,ResponseCategory
from rapidsms.models import Contact, Connection
from django.contrib.auth.models import User, Group
from django.contrib.sites.models import Site
from django.contrib.sites.managers import CurrentSiteManager
from django.conf import settings
from rapidsms.contrib.locations.models import Location
from eav.models import Attribute
from django.core.exceptions import ValidationError
from script.signals import *
from script.models import *
from script.utils.handling import find_closest_match, find_best_response
from rapidsms_httprouter.models import Message, MessageBatch
from unregister.models import Blacklist
from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from rapidsms_xforms.models import  XFormField
from ussd.models import ussd_pre_transition, ussd_complete, Navigation, TransitionException, Field, Question,StubScreen

import datetime
import re
import difflib


class IgnoredTags(models.Model):
    poll = models.ForeignKey(Poll)
    name = models.CharField(max_length=20)

    def __unicode__(self):
        return '%s' % self.name

class QuoteBox(models.Model):
    question = models.TextField()
    quote = models.TextField()
    quoted = models.TextField()
    creation_date = models.DateTimeField(auto_now=True)

    class Meta:
        get_latest_by = 'creation_date'

class TopResponses(models.Model):
    poll = models.ForeignKey(Poll, related_name="top_responses")
    quote = models.TextField()
    quoted = models.TextField()

class Ureporter(Contact):
    def age(self):
        if self.birthdate:
            return (datetime.datetime.now() - self.birthdate).days / 365
        else:
            return ""
    def is_active(self):
        return not Blacklist.objects.filter(connection=self.default_connection).exists()

    def join_date(self):
        ss = ScriptSession.objects.filter(connection__contact=self)
        if ss.exists():
            return ScriptSession.objects.filter(connection__contact=self)[0].start_time.date()
        else:
            messages = Message.objects.filter(connection=self.default_connection).order_by('date')
            if messages.exists():
                return messages[0].date
            else:
                return None

    def quit_date(self):
        quit_msg = Message.objects.filter(connection__contact=self,application="unregister")
        if quit_msg.exists():
            return quit_msg.latest('date').date
    def messages_count(self):
        return Message.objects.filter(connection__contact=self,direction="I").count()

    class Meta:
        proxy = True

def autoreg(**kwargs):
    connection = kwargs['connection']
    progress = kwargs['sender']
    if not progress.script.slug in ['ureport_autoreg', 'ureport_autoreg_luo','ureport_autoreg2', 'ureport_autoreg_luo2']:
        return

    connection.contact = Contact.objects.create(name='Anonymous User')
    connection.save()
    session = ScriptSession.objects.filter(script=progress.script, connection=connection).order_by('-end_time')[0]
    script = progress.script
    youthgrouppoll = script.steps.get(order=1).poll
    districtpoll = script.steps.get(order=3).poll
    namepoll = script.steps.get(order=5).poll
    agepoll = script.steps.get(order=6).poll
    genderpoll = script.steps.get(order=7).poll
    villagepoll = script.steps.get(order=8).poll
    contact = connection.contact
    name = find_best_response(session, namepoll)
    if name:
        contact.name = name[:100]

    contact.reporting_location = find_best_response(session, districtpoll)

    age = find_best_response(session, agepoll)
    if age and age < 100:
        contact.birthdate = datetime.datetime.now() - datetime.timedelta(days=(365 * int(age)))

    gresps = session.responses.filter(response__poll=genderpoll, response__has_errors=False).order_by('-response__date')
    if gresps.count():
        gender = gresps[0].response
        if gender.categories.filter(category__name='male').count():
            contact.gender = 'M'
        elif gender.categories.filter(category__name='female').exists():
            contact.gender = 'F'

    village = find_best_response(session, villagepoll)
    if village:
        contact.village = village

    group_to_match = find_best_response(session, youthgrouppoll)
    default_group = None
    if progress.language:
        contact.language = progress.language
    if Group.objects.filter(name='Other uReporters').count():
        default_group = Group.objects.get(name='Other uReporters')
    if group_to_match:
        for g in re.findall(r'\w+', group_to_match):
            if g:
                group = find_closest_match(str(g), Group.objects)
                if group:
                    contact.groups.add(group)
                    break

        if default_group:
            contact.groups.add(default_group)
    elif default_group:
        contact.groups.add(default_group)

    if not contact.name:
        contact.name = 'Anonymous User'
    contact.save()

    total_ureporters = Contact.objects.exclude(connection__identity__in=Blacklist.objects.values_list('connection__identity')).count()
    if total_ureporters % getattr(settings, 'USER_MILESTONE', 500) == 0:
        recipients = getattr(settings, 'ADMINS', None)
        if recipients:
            recipients = [email for name, email in recipients]
        mgr = getattr(settings, 'MANAGERS', None)
        if mgr:
            for email in mgr:
                recipients.append(email)
        send_mail("UReport now %d voices strong!" % total_ureporters, "%s (%s) was the %dth member to finish the sign-up.  Let's welcome them!" % (contact.name, connection.identity, total_ureporters), 'root@uganda.rapidsms.org', recipients, fail_silently=True)

def check_conn(sender, **kwargs):
    #delete bad connections
    c = kwargs['instance']
    if not c.identity.isdigit():
        c.delete()
def update_latest_poll(sender, **kwargs):
    poll=kwargs['instance']
    xf=XFormField.objects.get(name='latest_poll')
    xf.question=poll.question
    xf.command=poll.pk
    xf.save()
    ss=StubScreen.objects.get(slug='question_response')
    if ss.default_response:
        ss.text=poll.default_response
    else:
        ss.text="Thanks For Your Response."

def ussd_poll(sender, **kwargs):

    if not  sender.connection.contact:
        sender.connection.contact = Contact.objects.create(name='Anonymous User')
        sender.connection.save()

    if sender.navigations.filter(screen__slug='weekly_poll').exists():
        field=XFormField.objects.get(name="latest_poll")
        nav=sender.navigations.filter(screen__slug='weekly_poll').latest('date')
        poll=Poll.objects.get(pk=int(field.command.rsplit('_')[1]))
        msg=Message.objects.create(connection=sender.connection,text=nav.response,direction="I")
        resp = Response.objects.create(poll=poll, message=nav.response, contact=sender.connection.contact, date=nav.date)
        for category in poll.categories.all():
            for rule in category.rules.all():
                regex = re.compile(rule.regex, re.IGNORECASE)
                if resp.eav.poll_text_value:
                    if regex.search(nav.response):
                        if category.error_category:
                            resp.has_errors = True
                        rc = ResponseCategory.objects.create(response=resp, category=category)
                        break
    if sender.navigations.filter(screen__slug='send_report'):
        Message.objects.create(connection=sender.connection,text=sender.navigations.filter(screen__slug='send_report').latest('date').response,direction="I")



script_progress_was_completed.connect(autoreg, weak=False)
post_save.connect(check_conn, sender=Connection, weak=False)
post_save.connect(update_latest_poll, sender=Poll, weak=False)
ussd_complete.connect(ussd_poll, weak=False)

