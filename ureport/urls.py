from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template
from ureport.views import *
from ureport.utils import get_contacts, get_polls
from django.contrib.auth.decorators import login_required
from contact.forms import FreeSearchForm, DistictFilterForm, FilterGroupsForm, AssignGroupForm, MassTextForm
from generic.views import generic, generic_row, generic_dashboard
from generic.forms import StaticModuleForm
from generic.sorters import SimpleSorter
from unregister.forms import BlacklistForm
from ureport.forms import *

urlpatterns = patterns('',
    url(r'^ureport/$', tag_view,name="tag_view"),
    url(r'^ureport/polls/(?P<type>\w){0,1}/$', polls,{'template':'ureport/partials/all_polls.html'}),
    url(r'^ureport/polls/freeform/$', polls,{'template':'ureport/partials/freeform_polls.html','type':'t'}),
    url(r'^ureport/tag_cloud/$', tag_cloud),
    url(r'^ureport/pie_graph/$', pie_graph,name="pie_chart"),
    url(r'^ureport/piegraph_module/$', piegraph_module),
    url(r'^ureport/histogram/$', histogram,name="histogram"),
    url(r'^ureport/map/$', map,name="map"),
    url(r'^ureport/map/module/$', mapmodule),
    url(r'^ureport/dashboard/$', generic, {
        'model':Poll,
        'queryset':get_polls,
        'results_title':'Polls',
        'filter_forms':[],
        'action_forms':[],
        'objects_per_page':10,
        'partial_row':'ureport/partials/poll_row.html',
        'partial_header':'ureport/partials/partial_header_dashboard.html',
        'base_template':'ureport/dashboard.html',
        'selectable':False,
        'columns':[('Name', True, 'name', SimpleSorter()),
                 ('Question', True, 'question', SimpleSorter(),),
                 ('Start Date',True,'start_date', SimpleSorter(),),
                 ('# Participants', False, 'participants',None,),
                 ('Visuals',False,'visuals',None,),
                 ],
        'sort_column':'start_date',
        'sort_ascending':False,
    }, name="poll_dashboard"),
    url(r'^ureport/add_tag/$', add_drop_word),
    url(r'^ureport/delete_tag/$', delete_drop_word),
    url(r'^ureport/show_excluded/$', show_ignored_tags),
    url(r"^ureport/(\d+)/message_history/$", view_message_history),
    url(r'^ureport/timeseries/$',show_timeseries),
    url(r'^ureport/reporter/$', login_required(generic), {
        'model':Contact,
        'queryset':get_contacts,
        'results_title':'uReporters',
        'filter_forms':[FreeSearchForm, DistictFilterForm, FilterGroupsForm],
        'action_forms':[MassTextForm, AssignGroupForm, BlacklistForm],
        'objects_per_page':25,
        'partial_row':'ureport/partials/contacts_row.html',
        'base_template':'ureport/contacts_base.html',
        'columns':[('Name', True, 'name', SimpleSorter()),
                 ('Number', True, 'connection__identity', SimpleSorter(),),
                 ('Location',True,'reporting_location__name', SimpleSorter(),),
                 ('Group(s)', True, 'groups__name',SimpleSorter()),
                 ('Total Poll Responses',True,'responses__count',SimpleSorter()),
                 ('',False,'',None)],
    }, name="ureport-contact"),
    url(r'^ureport/reporter/(?P<reporter_pk>\d+)/edit', editReporter),
    url(r'^ureport/reporter/(?P<reporter_pk>\d+)/delete', deleteReporter),
    url(r'^ureport/reporter/(?P<pk>\d+)/show', generic_row, {'model':Contact, 'partial_row':'ureport/partials/contacts_row.html'}),
    url(r'^ureport/polls/$', login_required(generic),  {
        'model':Poll,
#        'queryset':get_contacts,
#        'filter_forms':[FreeSearchForm, DistictFilterForm, FilterGroupsForm],
#        'action_forms':[MassTextForm, AssignGroupForm, BlacklistForm],
        'objects_per_page':10,
        'selectable':False,
        'partial_row':'ureport/partials/poll_admin_row.html',
        'base_template':'ureport/poll_admin_base.html',
        'results_title':'Polls',
        'sort_column':'start_date',
        'sort_ascending':False,
        'columns':[('Name', True, 'name', SimpleSorter()),
                 ('Question', True, 'question', SimpleSorter(),),
                 ('Start Date',True,'start_date', SimpleSorter(),),
                 ('Closing Date', True, 'end_date',SimpleSorter()),
                 ('',False,'',None)],
    }, name="ureport-polls"),
    url(r"^ureport/(\d+)/responses/$", view_responses),
    url(r'^ureport/awesome/$', generic_dashboard,{
           'slug':'ureport',
        'module_types':[('ureport', PollModuleForm, 'uReport Visualizations',),
                        ('static', StaticModuleForm, 'Static Content',),],
        'base_template':'ureport/homepage.html',
        'title':None,
   }),
    url(r'^ureport/bestviz/$', best_visualization, name="best-viz"),
    url(r'^ureport/messagefeed/$', message_feed),
)