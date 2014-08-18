from pyramid.view import view_config

from phoenix.views.settings import SettingsView

import logging
logger = logging.getLogger(__name__)

class Overview(SettingsView):
    def __init__(self, request):
        super(Overview, self).__init__(request, 'Overview')
        self.settings = self.request.registry.settings

    @view_config(route_name='settings', renderer='phoenix:templates/settings/overview.pt')
    def view(self):
        buttongroups = []
        buttons = []

        buttons.append(dict(url=self.settings.get('supervisor.url'),
                            icon="monitor_edit.png", title="Supervisor", id="external-url"))
        buttons.append(dict(url="/settings/catalog", icon="bookshelf.png", title="Catalog"))
        buttons.append(dict(url="/settings/users", icon="user_catwomen.png", title="Users"))
        buttons.append(dict(url="/settings/jobs", icon="blackboard_sum.png", title="Jobs"))
        buttons.append(dict(url=self.settings.get('thredds.url'),
                            icon="unidataLogo.png", title="Thredds", id="external-url"))
        buttongroups.append(dict(title='Settings', buttons=buttons))

        return dict(buttongroups=buttongroups)
