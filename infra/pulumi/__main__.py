"""An Azure RM Python Pulumi program"""

import pulumi
import base64
from yaml import safe_load as parseYaml
import pulumi_random as random
import pulumi_azuread as azuread
from pulumi_azure_native import (
    resources,
    network,
    compute,
    dbforpostgresql,
    authorization,
    containerservice,
    managedidentity,
    containerregistry,
)


def generate_peering_name(vnet_a, vnet_b):
    return f"{vnet_a}-to-{vnet_b}-peering"


# Generate variables
client_config = authorization.get_client_config()
stack_config = pulumi.Config()
try:
    resource_prefix = stack_config.get("resourcePrefix")
    resource_tags = parseYaml(stack_config.get("resourceTags"))
    deployment_region = stack_config.get("deploymentRegion")
    whitelisted_ip_ranges = parseYaml(stack_config.get("whitelistedIpRanges"))
    ssh_public_key_path = stack_config.get("sshPublicKeyPath")
except KeyError or AttributeError as err:
    raise Exception(f"Error in configuration: \n{err}!")

rg01_name = f"{resource_prefix}-rg01"
vnet01_name = f"{resource_prefix}-vnet01"
vnet01_subnet01_name = f"{vnet01_name}-subnet01"
vm01_name = f"{resource_prefix}-vm01"
vm01_publicip01_name = f"{vm01_name}-publicip01"
vm01_nic01_name = f"{vm01_name}-nic01"
vnet01_subnet01_nsg01_name = f"{vnet01_subnet01_name}-nsg01"

rg02_name = f"{resource_prefix}-rg02"
privdnszone01_name = "private.postgres.database.azure.com"
dbsrv01_name = f"{resource_prefix}-dbsrv01"
vnet02_name = f"{resource_prefix}-vnet02"
vnet02_subnet01_name = f"{vnet02_name}-subnet01"

rg03_name = f"{resource_prefix}-rg03"
vnet03_name = f"{resource_prefix}-vnet03"
vnet03_subnet01_name = f"{vnet03_name}-subnet01"
privdnszone02_name = "privatelink.northcentralus.azmk8s.io"
aks01_name = f"{resource_prefix}-aks01"
aks01_admin_group_name = f"{aks01_name}-admins"

rg04_name = f"{resource_prefix}-rg04"
vnet04_name = f"{resource_prefix}-vnet04"
vnet04_subnet01_name = f"{vnet04_name}-subnet01"
# Minus not allowed in resource name
acr01_name = f"{resource_prefix}acr01"
privdnszone03_name = "privatelink.azurecr.io"

resource_tags.update({"app": "passwordlessdbapp"})
# Read ssh pubkey
with open(ssh_public_key_path, "r") as f:
    ssh_public_key = f.read()

# Read startup script
with open("resources/startup-script.sh", "r") as f:
    startup_script = f.read()

rg01 = resources.ResourceGroup(
    rg01_name,
    resource_group_name=rg01_name,
    location="eastus",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vnet01 = network.VirtualNetwork(
    vnet01_name,
    virtual_network_name=vnet01_name,
    resource_group_name=rg01.name,
    location=rg01.location,
    address_space={"address_prefixes": ["10.0.0.0/16"]},
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vnet01_subnet01_nsg01 = network.NetworkSecurityGroup(
    vnet01_subnet01_nsg01_name,
    network_security_group_name=vnet01_subnet01_nsg01_name,
    resource_group_name=rg01.name,
    location=rg01.location,
    security_rules=[
        {
            "name": "sshAllowFromHome",
            "priority": 100,
            "direction": "Inbound",
            "access": "Allow",
            "protocol": "TCP",
            "source_port_range": "*",
            "destination_port_range": "22",
            "source_address_prefixes": whitelisted_ip_ranges,
            "destination_address_prefixes": ["10.0.0.0/24"],
        },
    ],
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vnet01_subnet01 = network.Subnet(
    vnet01_subnet01_name,
    subnet_name=vnet01_subnet01_name,
    address_prefix="10.0.0.0/24",
    resource_group_name=rg01.name,
    virtual_network_name=vnet01.name,
    network_security_group={"id": vnet01_subnet01_nsg01.id},
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vm01_publicip01 = network.PublicIPAddress(
    vm01_publicip01_name,
    public_ip_address_name=vm01_publicip01_name,
    resource_group_name=rg01.name,
    location=rg01.location,
    public_ip_allocation_method="Dynamic",
    sku={"name": "Basic"},
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vm01_nic01 = network.NetworkInterface(
    vm01_nic01_name,
    network_interface_name=vm01_nic01_name,
    resource_group_name=rg01.name,
    location=rg01.location,
    ip_configurations=[
        {
            "name": f"{vm01_nic01_name}-ipcfg01",
            "subnet": {"id": vnet01_subnet01.id},
            "private_ip_address_allocation": "Dynamic",
            "public_ip_address": {"id": vm01_publicip01.id},
        }
    ],
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vm01 = compute.VirtualMachine(
    vm01_name,
    vm_name=vm01_name,
    resource_group_name=rg01.name,
    location=rg01.location,
    identity={"type": "SystemAssigned"},
    network_profile={
        "network_interfaces": [
            {
                "id": vm01_nic01.id,
            }
        ]
    },
    hardware_profile={"vm_size": "Standard_B2s"},
    storage_profile={
        "os_disk": {
            "create_option": "FromImage",
            "delete_option": "Delete",
            "caching": "ReadWrite",
            "name": f"{vm01_name}-disk01",
            "managed_disk": {"storage_account_type": "Standard_LRS"},
        },
        "image_reference": {
            "publisher": "Canonical",
            "offer": "0001-com-ubuntu-server-jammy",
            "sku": "22_04-lts",
            "version": "latest",
        },
    },
    os_profile={
        "custom_data": f"{base64.b64encode(startup_script.encode('ascii')).decode('ascii')}",
        "admin_username": "user01",
        "computer_name": vm01_name,
        "linux_configuration": {
            "disable_password_authentication": True,
            "ssh": {
                "public_keys": [
                    {
                        "key_data": ssh_public_key,
                        "path": "/home/user01/.ssh/authorized_keys",
                    }
                ]
            },
        },
    },
    opts=pulumi.ResourceOptions(
        delete_before_replace=True, replace_on_changes=["os_profile"]
    ),
)

rg02 = resources.ResourceGroup(
    rg02_name,
    resource_group_name=rg02_name,
    location="eastus2",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)


vnet02 = network.VirtualNetwork(
    vnet02_name,
    virtual_network_name=vnet02_name,
    resource_group_name=rg02.name,
    location=rg02.location,
    address_space={"address_prefixes": ["10.1.0.0/16"]},
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vnet02_subnet01 = network.Subnet(
    vnet02_subnet01_name,
    subnet_name=vnet02_subnet01_name,
    address_prefix="10.1.0.0/24",
    resource_group_name=rg02.name,
    virtual_network_name=vnet02.name,
    delegations=[
        {
            "name": "Microsoft.DBforPostgreSQL/flexibleServers",
            "service_name": "Microsoft.DBforPostgreSQL/flexibleServers",
        }
    ],
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

privdnszone01 = network.PrivateZone(
    f"{resource_prefix}-privdnszone01",
    private_zone_name=privdnszone01_name,
    location="Global",
    resource_group_name=rg02.name,
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

dbsrv01_pass = random.RandomPassword(
    f"{dbsrv01_name}-pass",
    length=16,
    special=True,
    override_special="!#$%&*()-_=+[]{}<>:?",
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

dbsrv01 = dbforpostgresql.Server(
    dbsrv01_name,
    server_name=dbsrv01_name,
    resource_group_name=rg02.name,
    location=rg02.location,
    maintenance_window={"custom_window": "DISABLED"},
    storage={
        "storage_size_gb": 32,
    },
    # backup={
    #     "backup_retention_days": 2,
    #     "geo_redundant_backup": "DISABLED",
    # },
    create_mode="DEFAULT",
    # high_availability={"mode": "DISABLED"},
    network={
        "delegated_subnet_resource_id": vnet02_subnet01.id,
        "private_dns_zone_arm_resource_id": privdnszone01.id,
    },
    version="14",
    auth_config={
        "active_directory_auth": "ENABLED",
        "password_auth": "ENABLED",
        "tenant_id": client_config.tenant_id,
    },
    identity={
        "type": "NONE",
    },
    replication_role="NONE",
    administrator_login_password=dbsrv01_pass.result,
    sku={"name": "Standard_B1ms", "tier": "Burstable"},
    administrator_login="dbadm",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

dbsrv01_database = dbforpostgresql.Database(
    f"{dbsrv01_name}-database-passwordlessdbapp01",
    charset="utf8",
    collation="en_US.utf8",
    database_name="passwordlessdbapp01",
    resource_group_name=rg02.name,
    server_name=dbsrv01.name,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

dbsrv01_database = dbforpostgresql.Database(
    f"{dbsrv01_name}-database-passwordlessdbapp02",
    charset="utf8",
    collation="en_US.utf8",
    database_name="passwordlessdbapp02",
    resource_group_name=rg02.name,
    server_name=dbsrv01.name,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)


dbsrv01_aad_admin01 = dbforpostgresql.Administrator(
    f"{dbsrv01_name}-aad-admin01",
    object_id=client_config.object_id,
    # apply() over apply()
    principal_name=dbsrv01.id.apply(
        lambda id: azuread.get_user_output(object_id=client_config.object_id)
    ).user_principal_name.apply(lambda user_principal_name: f"{user_principal_name}"),
    principal_type="User",
    resource_group_name=rg02.name,
    server_name=dbsrv01.name,
    tenant_id=client_config.tenant_id,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

privdnszone01_vnetlink01 = network.VirtualNetworkLink(
    f"{resource_prefix}-privdnszone01-vnetlink01-vnet01",
    private_zone_name=privdnszone01.name,
    resource_group_name=rg02.name,
    location="Global",
    registration_enabled=False,
    virtual_network={"id": vnet01.id},
    virtual_network_link_name=f"{resource_prefix}-privdnszone01-vnetlink01-vnet01",
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

# Make output dependent of existence of vnets using all()
combined_vnets = pulumi.Output.all(
    vnet01.id, vnet01_subnet01.id, vnet02.id, vnet02_subnet01.id
)
# First peering (vnet02 -> vnet01)
vnet02_to_vnet01_peering = combined_vnets.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet02_name, vnet01_name),
        virtual_network_peering_name=generate_peering_name(vnet02_name, vnet01_name),
        resource_group_name=rg02.name,
        virtual_network_name=vnet02.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet01.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=False,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        opts=pulumi.ResourceOptions(
            depends_on=[vnet01, vnet02],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

# Second peering (vnet01 -> vnet02)
vnet01_to_vnet02_peering = combined_vnets.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet01_name, vnet02_name),
        virtual_network_peering_name=generate_peering_name(vnet01_name, vnet02_name),
        resource_group_name=rg01.name,
        virtual_network_name=vnet01.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet02.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=True,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        opts=pulumi.ResourceOptions(
            depends_on=[vnet01, vnet02, vnet02_to_vnet01_peering],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

rg03 = resources.ResourceGroup(
    rg03_name,
    resource_group_name=rg03_name,
    location="northcentralus",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vnet03 = network.VirtualNetwork(
    vnet03_name,
    virtual_network_name=vnet03_name,
    resource_group_name=rg03.name,
    location=rg03.location,
    address_space={"address_prefixes": ["10.2.0.0/16"]},
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vnet03_subnet01 = network.Subnet(
    vnet03_subnet01_name,
    subnet_name=vnet03_subnet01_name,
    address_prefix="10.2.0.0/16",
    resource_group_name=rg03.name,
    virtual_network_name=vnet03.name,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

privdnszone02 = network.PrivateZone(
    f"{resource_prefix}-privdnszone02",
    private_zone_name=privdnszone02_name,
    location="Global",
    resource_group_name=rg03.name,
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

aks01_admin_group = azuread.Group(
    aks01_admin_group_name,
    display_name=aks01_admin_group_name,
    description=f"Admin group for {aks01_name} cluster",
    mail_nickname=aks01_admin_group_name,
    security_enabled=True,
    owners=[
        client_config.object_id,
    ],
    members=[
        vm01.identity.principal_id,
    ],
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

aks01_umi01 = managedidentity.UserAssignedIdentity(
    f"{aks01_name}-umi01",
    location=rg03.location,
    resource_group_name=rg03.name,
    resource_name_=f"{aks01_name}-umi01",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

aks01_workload_umi01 = managedidentity.UserAssignedIdentity(
    f"{aks01_name}-passwordlessdbapp-umi01",
    location=rg03.location,
    resource_group_name=rg03.name,
    resource_name_=f"{aks01_name}-passwordlessdbapp-umi01",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

# https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/networking#private-dns-zone-contributor
aks01_umi01_role_assignment = authorization.RoleAssignment(
    f"{aks01_name}-umi01-private-dns-zone-contributor-role-assignment",
    principal_id=aks01_umi01.principal_id,
    principal_type="ServicePrincipal",
    role_definition_id=f"/subscriptions/{client_config.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b12aa53e-6015-4669-85d0-8515ebb3ae7f",
    scope=rg03.id,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

aks01 = containerservice.ManagedCluster(
    aks01_name,
    location=rg03.location,
    resource_name_=aks01_name,
    resource_group_name=rg03_name,
    # TODO: test it!
    # linux_profile={
    #     "admin_username": "user01",
    #     "ssh": {
    #         "public_keys": [{
    #             "key_data": ssh_public_key,
    #         }],
    #     },
    # },
    api_server_access_profile={
        "disable_run_command": False,
        "enable_private_cluster": True,
        "enable_private_cluster_public_fqdn": False,
        "private_dns_zone": privdnszone02.id,
    },
    aad_profile={
        "admin_group_object_ids": [aks01_admin_group.object_id],
        "enable_azure_rbac": True,
        "managed": True,
        "tenant_id": client_config.tenant_id,
    },
    auto_upgrade_profile={
        "upgrade_channel": "stable",
    },
    disable_local_accounts=True,
    # Can't be used at the same time as fqdn_subdomain
    # dns_prefix=aks01_name,
    enable_rbac=True,
    fqdn_subdomain=aks01_name,
    identity={
        "type": "UserAssigned",
        "user_assigned_identities": [aks01_umi01.id],
    },
    agent_pool_profiles=[
        {
            "name": "sysnodepool",
            "node_labels": {
                "sysnodepool": "true",
            },
            "vnet_subnet_id": vnet03_subnet01.id,
            "enable_auto_scaling": False,
            "enable_encryption_at_host": False,
            "enable_fips": False,
            "enable_node_public_ip": False,
            "enable_ultra_ssd": False,
            "kubelet_disk_type": "OS",
            "mode": "System",
            "count": 1,
            # Not supported in northcentralus
            # "availability_zones": ["1"],
            "os_type": "Linux",
            "tags": resource_tags,
            "type": "VirtualMachineScaleSets",
            "upgrade_settings": {
                "max_surge": "1",
            },
            "vm_size": "Standard_B2s",
            "workload_runtime": "OCIContainer",
        }
    ],
    azure_monitor_profile={
        "metrics": {"enabled": False},
    },
    network_profile={
        "dns_service_ip": "172.16.0.10",
        "load_balancer_sku": "STANDARD",
        "network_plugin": "azure",
        "pod_cidrs": ["172.24.0.0/13"],
        "service_cidrs": ["172.16.0.0/14"],
        "network_plugin_mode": "overlay",
    },
    node_resource_group=f"{rg03_name}-aks01-res",
    oidc_issuer_profile={
        "enabled": True,
    },
    pod_identity_profile={
        "allow_network_plugin_kubenet": False,
        "enabled": False,
    },
    public_network_access="DISABLED",
    addon_profiles={},
    security_profile={
        "azure_key_vault_kms": {
            "enabled": False,
        },
        "defender": {
            "security_monitoring": {
                "enabled": False,
            },
        },
        "image_cleaner": {
            "enabled": True,
            "interval_hours": 240,
        },
        "workload_identity": {
            "enabled": True,
        },
    },
    sku={
        "name": "Base",
        "tier": "FREE",
    },
    storage_profile={
        "blob_csi_driver": {
            "enabled": False,
        },
        "disk_csi_driver": {
            "enabled": True,
        },
        "file_csi_driver": {
            "enabled": False,
        },
        "snapshot_controller": {
            "enabled": False,
        },
    },
    support_plan="KUBERNETES_OFFICIAL",
    tags=resource_tags,
    kubernetes_version="1.30.0",
    workload_auto_scaler_profile={
        "keda": {
            "enabled": False,
        },
    },
    opts=pulumi.ResourceOptions(
        depends_on=[privdnszone02, aks01_umi01_role_assignment],
        delete_before_replace=True,
    ),
)

# Role AKS RBAC Admin granted by default because it's admin group attached to cluster
aks01_admin_group_role_assignment = authorization.RoleAssignment(
    f"{aks01_admin_group_name}-azure-kubernetes-service-cluster-user-role-assignment",
    principal_id=aks01_admin_group.object_id,
    principal_type="Group",
    role_definition_id=f"/subscriptions/{client_config.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4abbcc35-e782-43d8-92c5-2d3f1bd2253f",
    scope=aks01.id,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

# First peering (vnet03 -> vnet01)
combined_vnet01_vnet03 = pulumi.Output.all(
    vnet01.id, vnet01_subnet01.id, vnet03.id, vnet03_subnet01.id
)

vnet03_to_vnet01_peering = combined_vnet01_vnet03.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet03_name, vnet01_name),
        virtual_network_peering_name=generate_peering_name(vnet03_name, vnet01_name),
        resource_group_name=rg03.name,
        virtual_network_name=vnet03.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet01.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=False,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        # Avoid "Resource is in Updating state" error
        opts=pulumi.ResourceOptions(
            depends_on=[vnet01, vnet03],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

# Second peering (vnet01 -> vnet03)
vnet01_to_vnet03_peering = combined_vnet01_vnet03.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet01_name, vnet03_name),
        virtual_network_peering_name=generate_peering_name(vnet01_name, vnet03_name),
        resource_group_name=rg01.name,
        virtual_network_name=vnet01.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet03.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=True,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        opts=pulumi.ResourceOptions(
            depends_on=[vnet01, vnet03, vnet03_to_vnet01_peering],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

# First peering (vnet03 -> vnet02)
combined_vnet02_vnet03 = pulumi.Output.all(
    vnet02.id, vnet02_subnet01.id, vnet03.id, vnet03_subnet01.id
)

vnet03_to_vnet02_peering = combined_vnet02_vnet03.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet03_name, vnet02_name),
        virtual_network_peering_name=generate_peering_name(vnet03_name, vnet02_name),
        resource_group_name=rg03.name,
        virtual_network_name=vnet03.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet02.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=True,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        # Avoid "Resource is in Updating state" error
        opts=pulumi.ResourceOptions(
            depends_on=[vnet02, vnet03],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

# Second peering (vnet02 -> vnet03)
vnet02_to_vnet03_peering = combined_vnet02_vnet03.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet02_name, vnet03_name),
        virtual_network_peering_name=generate_peering_name(vnet02_name, vnet03_name),
        resource_group_name=rg02.name,
        virtual_network_name=vnet02.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet03.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=False,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        opts=pulumi.ResourceOptions(
            depends_on=[vnet02, vnet03, vnet03_to_vnet02_peering],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

privdnszone01_vnetlink02 = network.VirtualNetworkLink(
    f"{resource_prefix}-privdnszone01-vnetlink02-vnet03",
    private_zone_name=privdnszone01.name,
    resource_group_name=rg02.name,
    location="Global",
    registration_enabled=False,
    virtual_network={"id": vnet03.id},
    virtual_network_link_name=f"{resource_prefix}-privdnszone01-vnetlink02-vnet03",
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

privdnszone02_vnetlink01 = network.VirtualNetworkLink(
    f"{resource_prefix}-privdnszone02-vnetlink01-vnet01",
    private_zone_name=privdnszone02.name,
    resource_group_name=rg03.name,
    location="Global",
    registration_enabled=False,
    virtual_network={"id": vnet01.id},
    virtual_network_link_name=f"{resource_prefix}-privdnszone02-vnetlink01-vnet01",
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

rg04 = resources.ResourceGroup(
    rg04_name,
    resource_group_name=rg04_name,
    location="northcentralus",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vnet04 = network.VirtualNetwork(
    vnet04_name,
    virtual_network_name=vnet04_name,
    resource_group_name=rg04.name,
    location=rg04.location,
    address_space={"address_prefixes": ["10.3.0.0/16"]},
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vnet04_subnet01 = network.Subnet(
    vnet04_subnet01_name,
    subnet_name=vnet04_subnet01_name,
    address_prefix="10.3.0.0/24",
    resource_group_name=rg04.name,
    virtual_network_name=vnet04.name,
    private_endpoint_network_policies="Disabled",
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

acr01 = containerregistry.Registry(
    f"{resource_prefix}-acr01",
    registry_name=acr01_name,
    location=rg04.location,
    resource_group_name=rg04.name,
    sku={"name": "Premium"},
    admin_user_enabled=False,
    data_endpoint_enabled=False,
    encryption={
        "status": "Disabled",
    },
    identity={
        "type": "SystemAssigned",
    },
    public_network_access="Disabled",
    zone_redundancy="Disabled",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

vm01_role_assignment = authorization.RoleAssignment(
    f"{vm01_name}-acr-push-role-assignment",
    principal_id=vm01.identity.principal_id,
    principal_type="ServicePrincipal",
    role_definition_id=f"/subscriptions/{client_config.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/8311e382-0749-4cb8-b61a-304f252e45ec",
    scope=acr01.id,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

aks01_agentpool_role_assignment = authorization.RoleAssignment(
    f"{aks01_name}-agentpool-acr-push-role-assignment",
    principal_id=aks01.identity_profile["kubeletidentity"].object_id,
    principal_type="ServicePrincipal",
    role_definition_id=f"/subscriptions/{client_config.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/7f951dda-4ed3-4680-a7ca-43fe172d538d",
    scope=acr01.id,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

privdnszone03 = network.PrivateZone(
    f"{resource_prefix}-privdnszone03",
    private_zone_name=privdnszone03_name,
    location="Global",
    resource_group_name=rg04.name,
    tags=resource_tags,
    opts=pulumi.ResourceOptions(depends_on=[acr01], delete_before_replace=True),
)

privdnszone02_vnetlink01 = network.VirtualNetworkLink(
    f"{resource_prefix}-privdnszone03-vnetlink01-vnet01",
    private_zone_name=privdnszone03.name,
    resource_group_name=rg04.name,
    location="Global",
    registration_enabled=False,
    virtual_network={"id": vnet01.id},
    virtual_network_link_name=f"{resource_prefix}-privdnszone04-vnetlink01-vnet01",
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

privdnszone02_vnetlink02 = network.VirtualNetworkLink(
    f"{resource_prefix}-privdnszone03-vnetlink02-vnet03",
    private_zone_name=privdnszone03.name,
    resource_group_name=rg04.name,
    location="Global",
    registration_enabled=False,
    virtual_network={"id": vnet03.id},
    virtual_network_link_name=f"{resource_prefix}-privdnszone04-vnetlink01-vnet03",
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

acr01_privendpoint01 = network.PrivateEndpoint(
    f"{resource_prefix}-acr01-privendpoint01",
    private_endpoint_name=f"{resource_prefix}-acr01-privendpoint01",
    resource_group_name=rg04.name,
    location=rg04.location,
    subnet={"id": vnet04_subnet01.id},
    private_link_service_connections=[
        {
            "name": f"{resource_prefix}-acr01-privendpoint01-peconn01",
            "group_ids": ["registry"],
            "private_link_service_id": acr01.id,
        }
    ],
    custom_network_interface_name=f"{resource_prefix}-acr01-privendpoint01-nic01",
    tags=resource_tags,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)

# Get nic in old way - save to state
# acr01_privendpoint01_nic = acr01_privendpoint01.network_interfaces.apply(
#     lambda network_interfaces: network_interfaces[0].id
# ).apply(
#     lambda nic_id: network.NetworkInterface.get(
#         "acr01_privendpoint01_nic01",
#         nic_id,
#         opts=pulumi.ResourceOptions(depends_on=[acr01_privendpoint01], ignore_changes=[]),
#     )
# )

# Get nic but make this action dependent of earlier acr01 provisioning using apply()
acr01_privendpoint01_nic = acr01_privendpoint01.id.apply(
    lambda id: network.get_network_interface_output(
        network_interface_name=acr01_privendpoint01.custom_network_interface_name,
        resource_group_name=rg04.name,
    )
)


acr01_recordset01 = network.PrivateRecordSet(
    f"{resource_prefix}-privdnszone03-record01",
    a_records=[
        {
            # RISK: it's not always the first NIC
            "ipv4_address": acr01_privendpoint01_nic.ip_configurations.apply(
                lambda nic_ip_configurations: f"{nic_ip_configurations[0].private_ip_address}"
            )
        }
    ],
    private_zone_name=privdnszone03.name,
    record_type="A",
    relative_record_set_name=pulumi.Output.format(
        "{0}.{1}.data", acr01.name, acr01.location
    ),
    resource_group_name=rg04.name,
    ttl=3600,
    opts=pulumi.ResourceOptions(
        depends_on=[acr01_privendpoint01], delete_before_replace=True
    ),
)

acr01_recordset02 = network.PrivateRecordSet(
    f"{resource_prefix}-privdnszone03-record02",
    a_records=[
        {
            # RISK: it's not always second NIC
            "ipv4_address": acr01_privendpoint01_nic.ip_configurations.apply(
                lambda nic_ip_configurations: f"{nic_ip_configurations[1].private_ip_address}"
            )
        }
    ],
    private_zone_name=privdnszone03.name,
    record_type="A",
    relative_record_set_name=acr01.name.apply(lambda name: f"{name}"),
    resource_group_name=rg04.name,
    ttl=3600,
    opts=pulumi.ResourceOptions(
        depends_on=[acr01_privendpoint01], delete_before_replace=True
    ),
)

# First peering (vnet01 -> vnet04)
combined_vnet01_vnet04 = pulumi.Output.all(
    vnet01.id, vnet01_subnet01.id, vnet04.id, vnet04_subnet01.id
)
vnet01_to_vnet04_peering = combined_vnet01_vnet04.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet01_name, vnet04_name),
        virtual_network_peering_name=generate_peering_name(vnet01_name, vnet04_name),
        resource_group_name=rg01.name,
        virtual_network_name=vnet01.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet04.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=True,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        opts=pulumi.ResourceOptions(
            depends_on=[vnet01, vnet04],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

# Second peering (vnet04 -> vnet01)
vnet04_to_vnet01_peering = combined_vnet01_vnet04.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet04_name, vnet01_name),
        virtual_network_peering_name=generate_peering_name(vnet04_name, vnet01_name),
        resource_group_name=rg04.name,
        virtual_network_name=vnet04.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet01.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=False,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        opts=pulumi.ResourceOptions(
            depends_on=[vnet01, vnet04, vnet01_to_vnet04_peering],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

# First peering (vnet03 -> vnet04)
combined_vnet03_vnet04 = pulumi.Output.all(
    vnet03.id, vnet03_subnet01.id, vnet04.id, vnet04_subnet01.id
)
vnet03_to_vnet04_peering = combined_vnet03_vnet04.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet03_name, vnet04_name),
        virtual_network_peering_name=generate_peering_name(vnet03_name, vnet04_name),
        resource_group_name=rg03.name,
        virtual_network_name=vnet03.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet04.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=True,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        opts=pulumi.ResourceOptions(
            depends_on=[vnet03, vnet04],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

# Second peering (vnet04 -> vnet03)
vnet04_to_vnet03_peering = combined_vnet03_vnet04.apply(
    lambda args: network.VirtualNetworkPeering(
        generate_peering_name(vnet04_name, vnet03_name),
        virtual_network_peering_name=generate_peering_name(vnet04_name, vnet03_name),
        resource_group_name=rg04.name,
        virtual_network_name=vnet04.name.apply(lambda name: f"{name}"),
        remote_virtual_network={"id": vnet03.id.apply(lambda id: f"{id}")},
        allow_virtual_network_access=False,
        allow_forwarded_traffic=False,
        allow_gateway_transit=False,
        use_remote_gateways=False,
        sync_remote_address_space=True,
        opts=pulumi.ResourceOptions(
            depends_on=[vnet04, vnet03, vnet03_to_vnet04_peering],
            custom_timeouts={"create": "5m", "update": "5m", "delete": "5m"},
            delete_before_replace=True,
        ),
    )
)

# Outputs
pulumi.export(
    "vm_ip_address",
    # Make output dependent of existence of vm01 using apply()
    vm01.id.apply(
        lambda id: network.get_public_ip_address_output(
            resource_group_name=rg01_name, public_ip_address_name=vm01_publicip01_name
        )
    ).ip_address,
)

pulumi.export(
    "database_password",
    dbsrv01_pass.result.apply(lambda password: pulumi.Output.secret(password)),
)

pulumi.export("vm_identity_name", vm01.name.apply(lambda name: name))
pulumi.export(
    "vm_identity_principal_id",
    vm01.identity.apply(lambda identity: identity.principal_id),
)

pulumi.export(
    "aks_workload_identity_name", aks01_workload_umi01.name.apply(lambda name: name)
)
pulumi.export(
    "aks_workload_identity_principal_id",
    aks01_workload_umi01.principal_id.apply(lambda principal_id: principal_id),
)
