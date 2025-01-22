#!/bin/bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

mkdir -p /etc/apt/keyrings
curl -sLS https://packages.microsoft.com/keys/microsoft.asc | \
    gpg --dearmor | tee /etc/apt/keyrings/microsoft.gpg > /dev/null
chmod go+r /etc/apt/keyrings/microsoft.gpg
AZ_DIST=$(lsb_release -cs)
echo "Types: deb
URIs: https://packages.microsoft.com/repos/azure-cli/
Suites: ${AZ_DIST}
Components: main
Architectures: $(dpkg --print-architecture)
Signed-by: /etc/apt/keyrings/microsoft.gpg" | tee /etc/apt/sources.list.d/azure-cli.sources
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.32/deb/Release.key | \
    gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
chmod 644 /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.32/deb/ /' | \
    tee /etc/apt/sources.list.d/kubernetes.list
chmod 644 /etc/apt/sources.list.d/kubernetes.list  
apt update -y
apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    postgresql-client-14 \
    azure-cli \
    kubectl \
    bash-completion \
    openjdk-17-jre-headless \
    podman
    
kubectl completion bash > /etc/bash_completion.d/kubectl
echo "#!/bin/bash
source /etc/bash_completion.d/kubectl
alias k=kubectl
complete -F __start_kubectl k" | tee /etc/profile.d/custom-999.sh
chmod +x /etc/profile.d/custom-999.sh
# https://azure.github.io/kubelogin/install.html#using-azure-cli
az aks install-cli
