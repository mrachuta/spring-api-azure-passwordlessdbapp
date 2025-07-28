## Project name
spring-api-azure-passwordlessdbapp - sample Spring Boot application to try Azure DevOps and access from VM/AKS to Azure Database for PostgreSQL with passwordless option enabled.

## Table of contents
- [Project name](#project-name)
- [Table of contents](#table-of-contents)
- [General info](#general-info)
- [Setup](#setup)
  - [Infra](#infra)
  - [Azure Pipelines](#azure-pipelines)
  - [Local development](#local-development)
  - [Production (VM)](#production-vm)
  - [Production (Kubernetes)](#production-kubernetes)
- [Usage](#usage)

## General info
App & stack is written basing on following documentation from Microsoft (and not only):
* https://learn.microsoft.com/en-us/azure/developer/java/spring-framework/configure-spring-data-jdbc-with-azure-postgresql
* https://learn.microsoft.com/en-us/azure/developer/java/spring-framework/deploy-passwordless-spring-database-app
* https://learn.microsoft.com/en-us/azure/developer/java/spring-framework/migrate-postgresql-to-passwordless-connection
* https://azure.github.io/azure-workload-identity/docs/quick-start.html
* https://learn.microsoft.com/en-us/azure/aks/workload-identity-deploy-cluster
* https://learn.microsoft.com/en-us/azure/aks/workload-identity-migrate-from-pod-identity
* https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli-managed-identity
* https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/docker
* https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/linux-agent
* https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/personal-access-token-agent-registration
* https://github.com/paolosalvatori/private-aks-cluster
* https://dmp.fabric8.io/#docker:build
* https://github.com/fabric8io/docker-maven-plugin/issues/1330#issuecomment-755308720

Skeleton of application was generated using Spring Boot generator with some manual changes: 
 * https://start.spring.io/#!type=maven-project&language=java&platformVersion=3.4.1&packaging=jar&jvmVersion=17&groupId=com.java.azure&artifactId=passwordlessdatabaseapp&name=passwordlessdatabaseapp&description=Demo%20project%20for%20Azure%20Passwordless&packageName=com.java.azure.passwordlessdatabaseapp&dependencies=azure-support,h2

Azure DevOps pipeline created with support of following articles:
* https://learn.microsoft.com/en-us/azure/devops/pipelines/process/run-number
* https://learn.microsoft.com/en-us/azure/devops/pipelines/process/variables
* https://learn.microsoft.com/en-us/azure/devops/pipelines/process/stages
* https://learn.microsoft.com/en-us/azure/devops/pipelines/process/set-secret-variables

## Setup

### Infra

1. Prepare environment. Ensure that you have virtualenvwrapper installed and configured.
    ```
    cd infra/pulumi/
    mkvirtualenv passwordlessdbapp
    pip3 install -r requirements.txt
    ```
2. Configure state file to be stored in local machine:
    ```
    pulumi login --local
    ```
3. To deploy resources, first, login to your Azure account using cli and optionally set a subscription (if you have more than one associated with your account) using the following commands:
    ```
    az login
    az account set --subscription "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    ```
    Then deploy resources:
    ```
    pulumi up -s dev
    ```
    NOTE: It will ask you to create secret passphrase to secure your configuration and secrets
4. Prepare database to accept passwordless connections:
    * VM.
      * Create SQL script on remote VM:
          ```
          export PULUMI_CONFIG_PASSPHRASE="<your_secret_passphrase>"

          ssh user01@$(pulumi stack -s dev output vm_ip_address) "cat << EOF > /tmp/entrascript.sql
          select * from pgaadauth_create_principal_with_oid('$(pulumi stack -s dev output vm_identity_name)', '$(pulumi stack -s dev output vm_identity_principal_id)', 'service', false, false);
          GRANT ALL PRIVILEGES ON DATABASE passwordlessdbapp01 TO \"$(pulumi stack -s dev output vm_identity_name)\";
          GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"$(pulumi stack -s dev output vm_identity_name)\";
          GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO \"$(pulumi stack -s dev output vm_identity_name)\";
          GRANT CREATE ON SCHEMA public TO \"$(pulumi stack -s dev output vm_identity_name)\";
          EOF
          "
          ```
      * SSH to your newly created remote VM:
          ```
          ssh user01@$(pulumi stack -s dev output vm_ip_address)
          ```
      * Get database details. Go to Azure Console -> Select your DB server -> Settings -> Connect and select 'postgres' database from dropdown list. Copy data and paste it on remote VM (export variables).
      * Login with your personal account. To grant AAD (Entra) permissions on database objects, you need to be Entra Admin. Commands:
          ```
          az login

          export PGUSER=$(az ad signed-in-user show --query userPrincipalName --output tsv)
          export PGPASSWORD=$(az account get-access-token --resource-type oss-rdbms --output tsv --query accessToken)

          psql -f /tmp/entrascript.sql
          az logout
          rm /tmp/entrascript.sql
          ```
    * Kubernetes
      * SSH to your newly created remote VM:
        ```
        ssh user01@$(pulumi stack -s dev output vm_ip_address)
        ```
      * Install az-cli extension and create Service Connector (don't worry, Azure will create namespace for you):
        ```
        az login

        az extension add --name serviceconnector-passwordless --upgrade

        az aks connection create postgres-flexible --connection passwordlessdbapp02 \
        --source-id $(az aks list --query "[?tags.app=='passwordlessdbapp'].id" --output tsv) \
        --target-id $(az postgres flexible-server list \
        --query "[?tags.app=='passwordlessdbapp'].id" --output tsv)/databases/passwordlessdbapp02 \
        --client-type springBoot --workload-identity $(az identity list --query "[?contains(name, 'passwordlessdbapp-umi01')].id" --output tsv) \
        --kube-namespace demo \
        --customized-keys \
        spring.datasource.azure.passwordless-enabled=SPRING_DATASOURCE_AZURE_PASSWORDLESSENABLED \
        spring.cloud.azure.credential.client-id=SPRING_CLOUD_AZURE_CREDENTIAL_CLIENTID \
        spring.cloud.azure.credential.managed-identity-enabled=SPRING_CLOUD_AZURE_CREDENTIAL_MANAGEDIDENTITYENABLED \
        spring.datasource.url=SPRING_DATASOURCE_URL spring.datasource.username=SPRING_DATASOURCE_USERNAME

        az logout
        ```

5. To destroy resources, run the following command:
    ```
    pulumi destroy -s dev
    ```


### Azure Pipelines

1. Guidelines are assuming that you already forked repository to Azure DevOps.
2. Generate Personal Access Token via web interface:
   [https://dev.azure.com/<your_organization_name>/_usersSettings/tokens](https://dev.azure.com/<your_organization_name>/_usersSettings/token) 
   
   and save it somewhere. Adjust permissions according your requirements. Token will be required later.
3. Create variable group and variables using cli:
    ```
    az login
    az extension add --name azure-devops

    az pipelines variable-group create \
    --name acr_registry \
    --variables acr_login=00000000-0000-0000-0000-000000000000 \
    acr_name=$(az acr list --query "[?tags.apps=='passwordlessdbapp'].name" --output tsv)
    ```
4. Create agentpool via web interface: 
   [https://dev.azure.com/<your_organization_name>/_settings/agentpools](https://dev.azure.com/<your_organization_name>/_settings/agentpools)

    * Click Add pool
    * Select Self-hosted
    * Name it 'my-pool'
5. SSH to your newly created remote VM:
    ```
    cd infra/pulumi/
    ssh user01@$(pulumi stack -s dev output vm_ip_address)
    ```
6. Perform following commands to pull git repository and to create agent image:
    ```
    git clone https://github.com/mrachuta/dockerfiles.git
    cd dockerfiles/azuredevops-agent

    podman build . -t localhost/azuredevops-agent:1.0
    ```
7. Run agent
    ```
    podman run -d \
    -e AZP_URL="https://dev.azure.com/<your_organization_name>/" \
    -e AZP_TOKEN="<your_personal_access_token>" \
    -e AZP_POOL="my-pool" \
    -e AZP_AGENT_NAME="my-pool-azp-agent-linux-podman" \
    --name "azp-agent-linux-podman" localhost/azuredevops-agent:1.0
    ```
8. Return to Azure DevOps UI and create new pipelines:
    * for *ci* pipeline select following file: *./azure/azure-pipelines-ci.yml*
    * for *cd* pipeline select following file: *./azure/azure-pipelines-cd.yml*
    * during first run of pipelines you will be asked for access to agent and secrets. You have to confirm this access.

### Local development

1. Clone git repository.
2. Go to root of repository and build application using Maven:
    ```
    ./mvnw clean package
    ```
3. Run application with specific profile:
    ```
    java -jar -Dspring.profiles.active=local target/passwordlessdbapp-0.0.1-SNAPSHOT.jar
    ```
4. (OPTIONAL) Build docker image:
   ```
    export DOCKER_HOST="unix:/tmp/storage-run-$(id -u)/podman/podman.sock"
    podman system service -t 600 &

    ./mvnw docker:build
   ```
5. (OPTIONAL) Push it to the repostiory (replace placeholders in commands first):
    ```
    az login

    podman login <your_registry_name>.azurecr.io -u 00000000-0000-0000-0000-000000000000 -p $(az acr login -n <your_registry_name> --expose-token -o tsv --query accessToken)

    podman tag localhost/spring-api-azure-passwordlessdbapp:<created_image_tag> <your_registry_name>/spring-api-azure-passwordlessdbapp:<created_image_tag>

    podman push <your_registry_name>/spring-api-azure-passwordlessdbapp:<created_image_tag>
    ```

### Production (VM)

1. Run application with environment variables set (replace placeholders with proper values):
    ```
    az login --identity

    DB_JDBC_STRING="jdbc:postgresql://<your_database_hostname>:5432/<your_database_name>?sslmode=require" DB_USERNAME="<your_vm_name>" java -jar target/passwordlessdbapp-0.0.1-SNAPSHOT.jar
    ```

### Production (Kubernetes)

1. Update kubernetes manifests located in [./infra/kubernetes/](infra/kubernetes/) and replace placeholders:
    ```
    az login --identity
    az aks get-credentials --name $(az aks list --query "[?tags.app=='passwordlessdbapp'].name" --output tsv) --resource-group $(az aks list --query "[?tags.app=='passwordlessdbapp'].resourceGroup" --output tsv) --overwrite-existing
    kubelogin convert-kubeconfig -l azurecli

    export IMAGE_PATH=<path_to_your_image_in_acr>
    export SA_NAME=$(k get sa -n demo -l azure.workload.identity/use=true -o jsonpath="{.items[0].metadata.name}")

    sed -i 's|<your_secret_name>|sc-passwordlessdbapp02-secret|g' infra/kubernetes/envs/example/kustomizaton.yaml
    sed -i "s|<your_image_path>|$IMAGE_PATH|g" infra/kubernetes/envs/example/kustomizaton.yaml
    sed -i "s|<your_serviceaccount_name>|$SA_NAME|g" infra/kubernetes/envs/example/kustomizaton.yaml
    ```
2. Deploy manifests
    ```
    kubectl create namespace demo || true
    cd infra/kubernetes/envs/example/
    kubectl apply -k .
    ```

## Usage

List objects in database:
```
curl -vk http://127.0.0.1:8080/
```
Kubernetes version:
```
kubectl run -it --rm curl -n demo --restart=Never \
--image=curlimages/curl \
-- curl -vk http://spring-api-azure-passwordlessdbapp-demo:8080/
```

Add object to database:
```
curl --header "Content-Type: application/json"  --request POST  \
--data '{"description":"configuration","details":"congratulations, you have set up JDBC correctly!","done": "true"}' \
http://127.0.0.1:8080/
```
Kubernetes version:
```
kubectl run -it --rm curl -n demo --restart=Never \
--image=curlimages/curl \
-- curl -vk --header "Content-Type: application/json" --request POST \
--data '{"description":"configuration","details":"congratulations, you have set up JDBC correctly!","done": "true"}' \
http://spring-api-azure-passwordlessdbapp-demo:8080/
```
