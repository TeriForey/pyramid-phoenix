from pyramid.view import view_config

from phoenix.wizard.views import Wizard
from phoenix.utils import user_cert_valid

import logging
logger = logging.getLogger(__name__)


def includeme(config):
    config.add_route('wizard_esgf_search', '/wizard/esgf_search')
    config.add_route('wizard_esgf_login', '/wizard/esgf_login')
    config.add_route('wizard_loading', '/wizard/loading')
    config.add_route('wizard_check_logon', '/wizard/check_logon.json')


class ESGFSearch(Wizard):
    def __init__(self, request):
        super(ESGFSearch, self).__init__(request, name='wizard_esgf_search', title="ESGF Search")

    def breadcrumbs(self):
        breadcrumbs = super(ESGFSearch, self).breadcrumbs()
        breadcrumbs.append(dict(route_path=self.request.route_path(self.name), title=self.title))
        return breadcrumbs

    def schema(self):
        from phoenix.schema import ESGFSearchSchema
        return ESGFSearchSchema()

    def next_success(self, appstruct):
        self.success(appstruct)

        # TODO: need to check pre conditions in wizard
        if not self.request.has_permission('submit') or user_cert_valid(self.request):
            return self.next('wizard_done')
        return self.next('wizard_esgf_login')

    @view_config(route_name='wizard_esgf_search', renderer='../templates/wizard/esgfsearch.pt')
    def view(self):
        return super(ESGFSearch, self).view()
