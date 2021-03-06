import json
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase
from poll.models import Poll
from rapidsms.models import Backend, Connection
from script.models import ScriptSession, Script
from ureport.tests.functional.views.api.helpers import TestBasicAuthMixin


class PollResponsesTestCase(TestCase, TestBasicAuthMixin):
    def test_that_url_for_poll_responses_returns_200(self):
        backend = Backend.objects.create(name="console")
        connection = Connection.objects.create(backend=backend, identity="999")
        script = Script.objects.create(slug="who")
        ScriptSession.objects.create(connection=connection, script=script)
        Poll.objects.create(id=900, user=User.objects.create(username="theone"), question="who")
        url = reverse("submit_poll_response_api", kwargs={"poll_id": 900, "backend": "console", "user_address": 999})
        data = {"response": True}
        response = self.client.post(url, data=json.dumps(data), content_type='application/json',
                                    **(self.get_auth_headers()))
        self.assertEqual(200, response.status_code)

    def test_404_is_thrown_if_backend_does_not_exist(self):
        response = self.client.post(
            reverse("submit_poll_response_api", kwargs={"poll_id": 1, "backend": "console", "user_address": 999}),
            **(self.get_auth_headers()))
        self.assertEqual(404, response.status_code)




