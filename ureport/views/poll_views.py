#!/usr/bin/python
# -*- coding: utf-8 -*-
from django.core.mail import send_mail
from django.shortcuts import render_to_response, get_object_or_404, redirect, render
from django.template import RequestContext
from django.views.decorators.vary import vary_on_cookie
from script.models import ScriptStep
from django.contrib.auth.decorators import login_required
from generic.views import generic
from django.views.decorators.cache import cache_control, never_cache
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from rapidsms_xforms.models import XFormField, XForm
from ureport.models.utils import recent_message_stats
from ussd.models import StubScreen
from poll.models import Poll, Category, Rule, Translation, Response
from poll.forms import CategoryForm, RuleForm2
from rapidsms.models import Contact
from ureport.forms import NewPollForm, GroupsFilter, SearchPollsForm
from django.conf import settings
from ureport.forms import AssignToPollForm, SearchResponsesForm, AssignResponseGroupForm, ReplyTextForm, DeleteSelectedForm
from django.contrib.sites.models import Site
from ureport import tasks
from ureport.utils import get_polls, get_script_polls, get_access
from generic.sorters import SimpleSorter
from ureport.views.utils.paginator import ureport_paginate
from django.db import transaction
from django.contrib.auth.models import Group
from ureport.models import UPoll, ExportedPoll
import logging, datetime
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext


log = logging.getLogger(__name__)


def start_poll_single_tx(poll):
    log.info("[start-poll-single-tx] Sending task to celery...")
    tasks.start_poll.delay(poll)
    log.info("[start-poll-single-tx] Sent to Celery Ok.")

# Right now this is a duplicate of the single_tx so we can test our feature toggle
def start_poll_multi_tx(poll):
    log.info("[start-poll-multi-tx] Sending task to celery...")
    tasks.start_poll.delay(poll)
    log.info("[start-poll-multi-tx] Sent to Celery Ok.")


@never_cache
@login_required
def poll_status(request, pk):
    poll = get_object_or_404(Poll, pk=pk)

    startDate = datetime.datetime.now()
    if 'startDate' in request.GET:
        startDate = datetime.datetime.strptime(request.GET.get('startDate'), "%Y-%m-%d")

    age_in_days = long(request.GET.get('age', '7'))

    template = 'ureport/polls/poll_status.html'

    message_stats = recent_message_stats(poll, startDate, age_in_days)

    return render_to_response(template, {
        'poll': poll,

        'message_stats_start_date': startDate,
        'message_stats_age_days': age_in_days,
        'message_stats': message_stats,
        }, context_instance=RequestContext(request))


@never_cache
@login_required
def view_poll(request, pk):
    poll = get_object_or_404(UPoll, pk=pk)
    groups = Group.objects.filter(pk__in=poll.contacts.values_list('groups'))
    category = None
    if request.GET.get('poll'):
        if request.GET.get('start'):
            poll = Poll.objects.get(pk=pk)
            if getattr(settings, 'START_POLL_MULTI_TX', False):
                start_poll_multi_tx(poll)
            else:
                start_poll_single_tx(poll)

            if getattr(settings, "FEATURE_PREPARE_SEND_POLL", False):
                res = """ <a href="?send=True&poll=True" data-remote=true  id="poll_action" class="btn">%s</a> """ \
                      % ugettext("Send Poll")
            else:
                res = """ <a href="?stop=True&poll=True" data-remote=true  id="poll_action" class="btn">%s</a> """ \
                      % ugettext("Close Poll")

            return HttpResponse(res)

        if request.GET.get('send'):
            log.info("[send-poll] queuing...")
            poll.queue_message_batches_to_send()
            log.info("[send-poll] done.")
            res = """ <a href="?stop=True&poll=True" data-remote=true  id="poll_action" class="btn">%s</a> """ \
                  % ugettext("Close Poll")
            return HttpResponse(res)

        if request.GET.get('stop'):
            poll.end()
            res = HttpResponse(
                """ <a href="?reopen=True&poll=True" data-remote=true id="poll_action" class="btn">%s</a> """
                % ugettext("Reopen Poll"))
            res['Cache-Control'] = 'no-store'
            return res
        if request.GET.get("reopen"):
            poll.end_date = None
            poll.save()
            res = HttpResponse(
                """<a href="?stop=True&poll=True" data-remote=true  id="poll_action" class="btn">%s</a>  """
                % ugettext("Close Poll"))
            res['Cache-Control'] = 'no-store'
            return res
        if request.GET.get('viewable'):
            poll.viewable = True
            poll.save()
            res = HttpResponse(
                '<a href="javascript:void(0)" id="poll_v" class="btn" onclick="loadViewable'
                '(\'?unviewable=True&poll=True\')">%s</a>'
                % ugettext("Don\'t Show On Home page"))
            res['Cache-Control'] = 'no-store'
            return res
        if request.GET.get('unviewable'):
            poll.viewable = False
            poll.save()
            res = HttpResponse(
                '<a href="javascript:void(0)" id="poll_v" class="btn" onclick="loadViewable'
                '(\'?viewable=True&poll=True\')">%s</a>' % ugettext("Show On Home page"))
            res['Cache-Control'] = 'no-store'
            return res
    x = XForm.objects.get(name='poll')
    xf, _ = XFormField.objects.get_or_create(name='latest_poll', xform=x, field_type=XFormField.TYPE_TEXT,
                                             command="poll_%d" % poll.pk)
    response = StubScreen.objects.get_or_create(slug='question_response')
    template = 'ureport/polls/view_poll.html'
    categories = poll.categories.all()
    category_form = CategoryForm()
    rule_form = RuleForm2()
    if request.method == "POST":
        if 'g_name' in request.POST:
            group, __ = Group.objects.get_or_create(name=request.POST.get('g_name'))
            cat = Category.objects.get(pk=request.POST.get('category'))
            tasks.group_up_category.delay(group, cat, request.user, Poll.objects.get(pk=pk))
            return HttpResponse("success")
        if request.GET.get('edit'):
            if request.POST.get('poll[default_response]'):
                poll.default_response = request.POST['poll[default_response]']
                poll.save()
            if request.POST.get('poll[question]'):
                poll.question = request.POST['poll[question]']
                poll.save()

        if request.GET.get("ussd", None):
            question = request.POST.get("question")
            response = request.POST.get("response")
            xf.question = question
            xf.save()
            response.text = response
            response.save()
        if request.GET.get("category", None):
            if request.GET.get('cat_pk'):
                category = Category.objects.get(pk=int(request.GET.get('cat_pk')))
            else:
                category = Category()
                category.poll = poll
            category_form = CategoryForm(request.POST, instance=category)
            if category_form.is_valid():
                template = "ureport/polls/rules.html"
                category = category_form.save()
                request.session['category'] = category
            else:
                template = "ureport/polls/category.html"

        if request.GET.get("rules", None):
            rule = Rule()
            rule.category = request.session['category']
            rule_form = RuleForm2(request.POST, instance=rule)
            if rule_form.is_valid:
                rule_form.save()
            else:
                template = "ureport/polls/rules.html"

    return render_to_response(template, {
        'poll': poll,
        'xf': xf,
        'response': response,
        'categories': categories,
        'category_form': category_form,
        'rule_form': rule_form,
        'category': category,
        'groups': groups,
        'FEATURE_PREPARE_SEND_POLL': getattr(settings, "FEATURE_PREPARE_SEND_POLL", False)
    }, context_instance=RequestContext(request))


@login_required
@transaction.commit_on_success
def new_poll(req):
    log.info("[new_poll] TRANSACTION START")
    if req.method == 'POST':
        log.info("[new-poll] - request recieved to create a poll")
        form = NewPollForm(req.POST, request=req)
        groups_form = GroupsFilter(req.POST, request=req)
        form.updateTypes()
        if form.is_valid() and groups_form.is_valid():
            # create our XForm
            is_urgent = form.cleaned_data['is_urgent']
            question = form.cleaned_data['question_en']
            default_response = form.cleaned_data['default_response_en']
            districts = form.cleaned_data['districts']
            excluded_groups = groups_form.cleaned_data['group_list']
            if hasattr(Contact, 'groups'):
                groups = form.cleaned_data['groups']

            log.info("[new-poll] - finding all contacts for this poll...")
            if len(districts):
                contacts = Contact.objects.filter(reporting_location__in=districts).filter(groups__in=groups).exclude(
                    groups__in=excluded_groups)
            else:
                contacts = Contact.objects.filter(groups__in=groups).exclude(groups__in=excluded_groups)

            log.info("[new-poll] - found all contacts ok.")

            log.info("[new-poll] - setting up translations...")
            name = form.cleaned_data['name']
            p_type = form.cleaned_data['type']
            response_type = form.cleaned_data['response_type']
            if not form.cleaned_data['default_response_luo'] == '' \
                and not form.cleaned_data['default_response_en'] == '':
                (translation, created) = \
                    Translation.objects.get_or_create(language='ach',
                                                      field=form.cleaned_data['default_response_en']
                    )
                translation.value = form.cleaned_data['default_response_luo']
                translation.save()
            if not form.cleaned_data['default_response_kdj'] == '' \
                and not form.cleaned_data['default_response_en'] == '':
                (translation, created) = \
                    Translation.objects.get_or_create(language='kdj',
                                                      field=form.cleaned_data['default_response_en']
                    )
                translation.value = form.cleaned_data['default_response_kdj']
                translation.save()
            if not form.cleaned_data['question_luo'] == '':
                (translation, created) = \
                    Translation.objects.get_or_create(language='ach',
                                                      field=form.cleaned_data['question_en']
                    )
                translation.value = form.cleaned_data['question_luo']
                translation.save()
            if not form.cleaned_data['question_kdj'] == '':
                (translation, created) = \
                    Translation.objects.get_or_create(language='kdj',
                                                      field=form.cleaned_data['question_en']
                    )
                translation.value = form.cleaned_data['question_kdj']
                translation.save()
            log.info("[new-poll] - translations ok.")

            poll_type = (Poll.TYPE_TEXT if p_type
                                           == NewPollForm.TYPE_YES_NO else p_type)

            poll = Poll.create_with_bulk(
                name,
                poll_type,
                question,
                default_response,
                contacts,
                req.user,
                is_urgent=is_urgent)

            if p_type == NewPollForm.TYPE_YES_NO:
                log.info("[new-poll] - is Y/N poll so adding categories...")
                poll.add_yesno_categories()
                log.info("[new-poll] - categories added ok.")

            if settings.SITE_ID:
                log.info("[new-poll] - SITE_ID is set, so adding the site to the poll")
                poll.sites.add(Site.objects.get_current())
                log.info("[new-poll] - site added ok")

            log.info("[new-poll] - poll created ok.")
            log.info("[new_poll] TRANSACTION COMMIT")
            return redirect(reverse('ureport.views.view_poll', args=[poll.pk]))

    else:
        form = NewPollForm(request=req)
        groups_form = GroupsFilter(request=req)
        form.updateTypes()

        log.info("[new_poll] TRANSACTION COMMIT")
    return render_to_response('ureport/new_poll.html', {'form': form, 'groups_form': groups_form},
                                  context_instance=RequestContext(req))


@cache_control(no_cache=True, max_age=0)
def poll_summary(request, poll=None):
    share = False
    script_polls = \
        ScriptStep.objects.exclude(poll=None).values_list('poll',
                                                          flat=True)
    excluded_polls = [297, 296, 349, 350, 420]
    polls = \
        Poll.objects.exclude(pk__in=script_polls).exclude(pk__in=excluded_polls).exclude(start_date=None).order_by(
            '-start_date')
    if not polls.exists():
        polls = None
    if poll:
        poll = get_object_or_404(Poll, pk=poll)
        polls = [poll]
        share = True
    else:
        poll = polls[0]
    if polls:
        return render_to_response('ureport/poll_summary.html', {'polls'
                                                                : polls, 'poll': poll, 'share': share},
                                context_instance=RequestContext(request))
    else:
        return render_to_response('ureport/poll_empty.html',
                                  context_instance=RequestContext(request))


@login_required
@transaction.commit_on_success
def view_responses(req, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    access = get_access(req)
    if access and not poll.user == access.user:
        return render(req, '403.html', status=403)

    script_polls = \
        ScriptStep.objects.exclude(poll=None).values_list('poll',
                                                          flat=True)
    response_rates = {}
    if poll.pk in script_polls:
        responses = poll.responses.order_by('-date')
        log.info("[reponses] 1 - %s " % responses)
    else:
        responses = poll.responses.all()
        responses = responses.order_by('-date')
        log.info("[reponses] 3 - %s " % responses)
        for group in req.user.groups.all():
            try:
                contact_count = \
                    poll.contacts.filter(groups__in=[group]).distinct().count()
                response_count = \
                    poll.responses.filter(contact__groups__in=[group]).distinct().count()
                response_rates[str(group.name)] = [contact_count]
                response_rates[str(group.name)].append(response_count)
                response_rates[str(group.name)].append(response_count
                                                       * 100.0 / contact_count)
            except ZeroDivisionError:
                response_rates.pop(group.name)
    typedef = Poll.TYPE_CHOICES[poll.type]
    # columns = [('Sender', False, 'sender', None)]
    # for (column, style_class, sortable, db_field, sorter) in \
    #     typedef['report_columns']:
    #     columns.append((column, sortable, db_field, sorter))
    columns = (
        (_('Date'), True, 'date', SimpleSorter()),
        (_('Text'), True, 'poll__question', SimpleSorter()),
        (_('Category'), True, 'categories__category', SimpleSorter())
    )

    return generic(
        req,
        model=Response,
        response_rates=response_rates,
        queryset=responses,
        objects_per_page=25,
        selectable=True,
        partial_base='ureport/partials/polls/poll_partial_base.html',
        base_template='ureport/responses_base.html',
        paginator_template='ureport/partials/new_pagination.html',
        paginator_func=ureport_paginate,
        row_base=typedef['view_template'],
        action_forms=[AssignToPollForm, AssignResponseGroupForm, ReplyTextForm,
                      DeleteSelectedForm],
        filter_forms=[SearchResponsesForm],
        columns=columns,
        partial_row='ureport/partials/polls/response_row.html',
        poll_id=poll_id,
        )


@login_required
@transaction.commit_on_success
def edit_category(request, pk):
    category = Category.objects.get(pk=int(pk))
    category_form = CategoryForm(instance=category)
    title = "Editing " + category.name
    return render_to_response("ureport/polls/category.html",
                              {'category': category, 'category_form': category_form, 'edit': True, "title": title},
                              context_instance=RequestContext(request))


@login_required
@transaction.commit_on_success
def delete_category(request, pk):
    category = Category.objects.get(pk=int(pk))
    category.delete()
    return HttpResponse(status=200)


@login_required
@transaction.autocommit
def delete_rule(request, pk):
    rule = Rule.objects.get(pk=int(pk))
    rule.delete()
    return HttpResponse(status=200)


@login_required
def view_rules(request, pk):
    category = Category.objects.get(pk=int(pk))
    rules = category.rules.all()
    rule = Rule()
    rule.category = category
    rule_form = RuleForm2(instance=rule)
    return render_to_response("ureport/polls/rules.html",
                              {'rules': rules, 'rule_form': rule_form, 'category': category, "edit": True},
                              context_instance=RequestContext(request))


@login_required
@transaction.commit_on_success
def create_rule(request, pk):
    rule_form = RuleForm2(request.POST or None)
    category = Category.objects.get(pk=int(pk))

    if rule_form.is_valid():
        rule = rule_form.save(commit=False)
        rule.category = category
        rule.save()
        tasks.reprocess_responses.delay(category.poll)
        if rule.rule == 1:
            r = _("Contains all of")
        else:
            r = _("Contains one of")
        res = """<td>%s</td><td>%s</td><td> <a  onclick="$(this).parent().parent().remove();" href="/rule/%d/delete/" data-remote=true> %s</a></td>""" % (
            r, rule.rule_string, rule.pk, _("Delete"))

        return HttpResponse(res)
    return HttpResponse("<td colspan='2'>%s</td>" % _("Please enter all the fields"))


@login_required
def poll_dashboard(request):
    columns = [(_('Name'), True, 'name', SimpleSorter()),
               (_('Question'), True, 'question', SimpleSorter(),),
               (_('Start Date'), True, 'start_date', SimpleSorter(),),
               (_('# Participants'), False, 'participants', None,),
               (_('Visuals'), False, 'visuals', None,),
               ]
    return generic(request,
                   model=Poll,
                   queryset=get_polls,
                   results_title='Polls',
                   objects_per_page=10,
                   partial_row='ureport/partials/dashboard/poll_row.html',
                   partial_header='ureport/partials/dashboard/partial_header_dashboard.html',
                   base_template='ureport/dashboard.html',
                   paginator_template='ureport/partials/new_pagination.html',
                   paginator_func=ureport_paginate,
                   selectable=False,
                   sort_column='start_date',
                   columns=columns
    )


@login_required
@vary_on_cookie
def ureport_polls(request, pk):
    access = get_access(request)
    columns = [(_('Name'), True, 'name', SimpleSorter()),
               (_('Question'), True, 'question', SimpleSorter(),),
               (_('Start Date'), True, 'start_date', SimpleSorter(),),
               (_('Closing Date'), True, 'end_date', SimpleSorter()),
               ('', False, '', None)]
    queryset = get_polls(request=request)
    if access:
        queryset = queryset.filter(user=access.user)
    return generic(request,
                   model=Poll,
                   queryset=queryset,
                   objects_per_page=10,
                   selectable=False,
                   partial_row='ureport/partials/polls/poll_admin_row.html',
                   base_template='ureport/poll_admin_base.html',
                   paginator_template='ureport/partials/new_pagination.html',
                   results_title='Polls',
                   paginator_func=ureport_paginate,
                   sort_column='start_date',
                   sort_ascending=False,
                   filter_forms=[SearchPollsForm],
                   columns=columns
    )


@login_required
def script_polls(request):
    columns = [('Name', True, 'name', SimpleSorter()),
               ('Question', True, 'question', SimpleSorter(),),
               ('Start Date', True, 'start_date', SimpleSorter(),),
               ('Closing Date', True, 'end_date', SimpleSorter()),
               ('', False, '', None)]
    return generic(request,
                   model=Poll,
                   queryset=get_script_polls,
                   objects_per_page=10,
                   selectable=False,
                   partial_row='ureport/partials/polls/poll_admin_row.html',
                   base_template='ureport/poll_admin_base.html',
                   paginator_template='ureport/partials/new_pagination.html',
                   paginator_func=ureport_paginate,
                   results_title='Polls',
                   sort_column='start_date',
                   auto_reg=True,
                   sort_ascending=False,
                   columns=columns)


@login_required
@never_cache
def start_poll_export(request, poll_id):
    poll = get_object_or_404(UPoll, pk=poll_id)
    if ExportedPoll.objects.filter(poll__pk=poll_id).exists():
        user = request.user
        if user.email:
            msg = "Hi %s,\nThe poll(%s) has been exported and is now ready for download." \
                  "\nPlease find it here %s\nThank You" % (
                      user.username, poll.name, poll.get_export_path(request.get_host()))
            send_mail('Contacts Added to Group', msg, "", [user.email], fail_silently=False)
    else:
        tasks.export_poll.delay(poll.pk, request.get_host(), username=request.user.username)
    return HttpResponse(status=200)
