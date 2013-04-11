from datetime import datetime
from django.contrib.auth.models import User, Group
from poll.models import Poll
from rapidsms.models import Contact,Connection, Backend

def create_group(group_name):
    group = Group.objects.create(name=group_name)
    return group


def create_user(username,email,group):
    user1 = User.objects.create(username=username, email=email)
    user1.groups.add(group)
    user1.save()
    return user1

def create_connection(identity,contact, backend):
    conn1 = Connection.objects.create(identity=identity, backend=backend)
    conn1.contact = contact
    conn1.save()


def create_poll_and_add_contacts_to_poll(contacts,user):
    poll_name = "functional_test"
    question = "from FT with love!"
    poll = Poll.objects.create(name=poll_name, question=question, user=user, type=Poll.TYPE_TEXT)
    for contact in contacts:
        poll.contacts.add(contact)
    poll.save()
    return poll


def start_poll_queues_messages_in_table(driver):

    group = create_group(group_name='groupFT')
    user1 = create_user(username="foo",email='foo@bar.com', group=group)
    user2 = create_user(username='fred', email='shaggy@scooby.com', group=group)

    contact1 = Contact.objects.create(pk=999, name='FT1', user=user1, gender='M',birthdate=datetime.now(),language="en")
    contact2 = Contact.objects.create(pk=1000, name='FT2', user=user2, gender='M',birthdate=datetime.now(),language="en")
    contacts = [contact1,contact2]

    backend=Backend.objects.create(name='test_backend')
    create_connection(identity='0794339344',contact=contact1,backend=backend)
    create_connection(identity='0794339427',contact=contact2,backend=backend)

    poll = create_poll_and_add_contacts_to_poll(contacts, user2)

    driver.create_and_sign_in_admin("argha","a")

    driver.open("/view_poll/%s" % poll.id)
    driver.browser.find_link_by_text('Start Poll').first.click()

    assert driver.browser.is_text_present('Close Poll')

    return poll.id,poll.contacts.count()
