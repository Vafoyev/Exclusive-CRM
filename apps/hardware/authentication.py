class HardwareAPIUser:
    is_authenticated = True
    is_anonymous = False
    role = 'hardware_agent'

    def __init__(self, integration):
        self.integration = integration
        self.organization = integration.organization
        self.id = None

    def __str__(self):
        return f"HardwareAgent<{self.organization_id}>"

    @property
    def organization_id(self):
        return self.organization.id if self.organization else None

