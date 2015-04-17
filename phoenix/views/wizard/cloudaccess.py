from pyramid.view import view_config

from phoenix.views.wizard import Wizard
from phoenix.models import get_folders

class CloudAccess(Wizard):
    def __init__(self, request):
        super(CloudAccess, self).__init__(
            request, name='wizard_cloud_access', title="Swift Cloud Access")
        self.process = request.wps.describeprocess(identifier='cloud_download')
        self.description = None

    def schema(self):
        from phoenix.schema import CloudAccessSchema
        user = self.get_user()
        storage_url = user.get('swift_storage_url')
        auth_token = user.get('swift_auth_token')
            
        return CloudAccessSchema().bind(containers=get_folders(storage_url, auth_token))

    def next_success(self, appstruct):
        self.success(appstruct)
        return self.next('wizard_done')
    
    @view_config(route_name='wizard_cloud_access', renderer='phoenix:templates/wizard/default.pt')
    def view(self):
        return super(CloudAccess, self).view()
    
