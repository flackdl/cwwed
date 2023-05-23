# Production

### Create Kubernetes cluster

**NOTE: currently using kops `1.25`, kubernetes `1.23`, kubectl `1.25`**.

Create Kubernetes cluster via [kops](https://github.com/kubernetes/kops).

    kops create cluster --master-count 1 --node-count 2 --master-size t3.medium --node-size t3.medium --zones us-east-1a --name cwwed-ingress-cluster.k8s.local --state=s3://cwwed-kops-state --yes
    
If necessary, configure kubectl environment to point at aws cluster:

    kops export kubecfg --name cwwed-ingress-cluster.k8s.local --state=s3://cwwed-kops-state

#### Setup RDS (relational database service) with proper VPC (from cluster) and security group permissions.

Do this in the AWS Console.

#### Create EFS

See:
- Docs: https://github.com/kubernetes-sigs/aws-efs-csi-driver/
- Sub Path: https://github.com/kubernetes-sigs/aws-efs-csi-driver/tree/master/examples/kubernetes/volume_path
- Static Path: https://github.com/kubernetes-sigs/aws-efs-csi-driver/tree/master/examples/kubernetes/multiple_pods

Deploy:

    kubectl apply -k "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/ecr/?ref=release-1.0"

Create EFS (elastic file system) in console and **make sure** it's in the same region, VPC and security group as the cluster.

Follow above instructions and make sure to edit the security group to allow the inbound NFS connections from our VPC's subnet.

Copy the `File System Id` from the new efs instance and update `configs/aws-efs.yml` accordingly (with deployment sub-paths).

Create kubernetes persistent volume & claim with the new efs instance:

    # apply efs volume configs (can take a couple minutes to create the provisioner pod)
    kubectl apply -f configs/aws-efs.yaml

### Nginx Ingress

Use nginx as the kubernetes ingress.

See https://kubernetes.github.io/ingress-nginx/.

Deploy:

    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.2.0/deploy/static/provider/aws/deploy.yaml

Configure:

    kubectl apply -f configs/ingress.yml

##### Load Balancing

The *nginx ingress* will automatically create an AWS Load Balancer.
Once the nginx ingress service is created,
monitor the new external Load Balancer and get its external IP address.

    kubectl get service --namespace ingress-nginx ingress-nginx-controller

Use that IP and configure DNS via Cloudflare.

### Autoscaler

##### Cluster autoscaler

See https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler and
[some other instructions I followed](https://varlogdiego.com/kubernetes-cluster-with-autoscaling-on-aws-and-kops) which showed it was
necessary to edit the kops `nodes` instance group and include some tags referenced by [cluster-autoscaler.yml](configs/cluster-autoscaler.yml).

Add the following *cloudLabels* via `kops edit instancegroups nodes`:

    cloudLabels:
        k8s.io/cluster-autoscaler/enabled: ""

Defining the `<YOUR_CLUSTER_NAME>` tag seems optional at this point, though, since we only have one cluster.

**NOTE**: make sure the CA version matches the k8s version.

**NOTE**: a rolling update is necessary.

##### Metrics Server

The Metrics Server is required for the HPA (horizontal pod scaler) to work.

It's necessary to follow the [kops specific instructions](https://github.com/kubernetes/kops/blob/master/addons/metrics-server/README.md)
which requires you to update the cluster, perform a rolling-update and then apply the [metrics-server](configs/metrics-server.yml) which added a couple
extra command line arguments.

Install the actual metrics server:

    kubectl apply -f configs/metrics-server.yml

Test the results after a couple minutes:

    kubectl top node

##### Horizontal Pod Autoscaler (hpa)

See https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/ and https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/.

Define autoscaling rules for the following deployments:

	kubectl autoscale deployment cwwed-alpha --min=2 --max=5
	kubectl autoscale deployment celery-celery-worker-alpha --min=2 --max=5

### Secrets

Create secrets using proper stage.  Update `$DEPLOY_STAGE` to **dev**, **alpha** etc.

    DEPLOY_STAGE=alpha

*NOTE:* always create new secrets with `echo -n "SECRET"` to avoid newline characters.

Create new secrets:

    kubectl create secret generic cwwed-secrets-$DEPLOY_STAGE \
        --from-literal=DATABASE_URL=$(cat ~/Documents/cwwed/secrets/$DEPLOY_STAGE/database_url.txt) \
        --from-literal=CWWED_HOST=$(cat ~/Documents/cwwed/secrets/$DEPLOY_STAGE/host.txt) \
        --from-literal=CWWED_NSEM_PASSWORD=$(cat ~/Documents/cwwed/secrets/cwwed_nsem_password.txt) \
        --from-literal=SECRET_KEY=$(cat ~/Documents/cwwed/secrets/secret_key.txt) \
        --from-literal=SLACK_BOT_TOKEN=$(cat ~/Documents/cwwed/secrets/slack_bot_token.txt) \
        --from-literal=CWWED_ARCHIVES_ACCESS_KEY_ID=$(cat ~/Documents/cwwed/secrets/cwwed_archives_access_key_id.txt) \
        --from-literal=CWWED_ARCHIVES_SECRET_ACCESS_KEY=$(cat ~/Documents/cwwed/secrets/cwwed_archives_secret_access_key.txt) \
        --from-literal=CELERY_FLOWER_USER=$(cat ~/Documents/cwwed/secrets/celery_flower_user.txt) \
        --from-literal=CELERY_FLOWER_PASSWORD=$(cat ~/Documents/cwwed/secrets/celery_flower_password.txt) \
        --from-literal=EMAIL_HOST_PASSWORD=$(cat ~/Documents/cwwed/secrets/sendgrid-api-key.txt) \
        --from-literal=SENTRY_DSN=$(cat ~/Documents/cwwed/secrets/sentry_dsn.txt) \
        && true
        
Create *kube-system* secrets:

    kubectl --namespace kube-system create secret generic cwwed-secrets-kube-system \
        --from-literal=AUTOSCALER_ACCESS_KEY_ID=$(cat ~/Documents/cwwed/secrets/aws_autoscaler_access_key_id.txt) \
        --from-literal=AUTOSCALER_SECRET_ACCESS_KEY=$(cat ~/Documents/cwwed/secrets/aws_autoscaler_secret_access_key.txt) \
        && true

To patch/update secrets, you must delete & then recreate:

    kubectl delete secret cwwed-secrets-$DEPLOY_STAGE

### Install all the services, volumes, deployments etc.

For yaml templates, use [emrichen](https://github.com/con2/emrichen) to generate yaml and pipe to `kubectl`.

For instance, deploy CWWED by defining the *deploy_stage* and cwwed image *tag*:

Deploy *alpha* using *latest* image tag:

    emrichen --define deploy_stage=alpha --define tag=latest configs/deployment-cwwed.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha --define tag=latest configs/service-cwwed.in.yml | kubectl apply -f -

    # celery default queue
    emrichen --define deploy_stage=alpha --define tag=latest --define queues=celery configs/deployment-celery.in.yml | kubectl apply -f -

    # celery beat (scheduled tasks)
    # TODO - use kustomize for better yaml templating
    # manually edit `configs/deployment-celery.in.yml` and swap the celery command argument, and change replicas to *1*
    emrichen --define deploy_stage=alpha --define tag=latest --define celery_type=beat configs/deployment-celery.in.yml | kubectl apply -f -

    # celery process-psa queue: single process, higher resource usage
    emrichen --define deploy_stage=alpha --define tag=latest --define queues=process-psa --define request_cpu=200m --define request_memory=1200M  --define concurrency=1 configs/deployment-celery.in.yml | kubectl apply -f -

    emrichen --define deploy_stage=alpha configs/deployment-opendap.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha configs/service-opendap.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha configs/deployment-redis.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha configs/service-redis.in.yml | kubectl apply -f -

Deploy *dev* using *v1.0* image tag:

    emrichen --define deploy_stage=dev --define tag=v1.0 configs/deployment-cwwed.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev --define tag=v1.0 configs/service-cwwed.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev --define tag=v1.0 configs/deployment-celery.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev configs/deployment-opendap.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev configs/service-opendap.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev configs/deployment-redis.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev configs/service-redis.in.yml | kubectl apply -f -

**OPTIONAL** define yaml templates for the following:

    kubectl apply -f configs/deployment-celery-flower.yml
    kubectl apply -f configs/service-celery-flower.yml

#### Everything else:

##### OPeNDAP

CWWED is using the stock OPeNDAP docker image, but we need to specify some custom configurations.
Copy the [olfs.xml](../configs/opendap/olfs.xml) to the EFS mount at (`OPENDAP-olfs` => `/usr/share/olfs/`) by ssh'ing into an EC2 instance, mounting the EFS drive, and copy it over.

##### Cluster Autoscaler

See https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md.

*NOTE*: the [cluster autoscaler](#autoscaler) instructions should have already been applied.

Apply cluster autoscaler:

    kubectl apply -f configs/cluster-autoscaler.yml

**NOTE**: we must define the `YOUR_CLUSTER_NAME` tag when moving to multiple clusters.  See [cluster-autoscaler.yml](configs/cluster-autoscaler.yml) and
https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md#auto-discovery-setup

### Initializations

Create the default super user:

    kubectl exec -it $CWWED_POD python manage.py createsuperuser

Run initializations like creating the "nsem" user and assigning permissions:

    kubectl exec -it $CWWED_POD python manage.py cwwed-init

Create cache tables:

*This should have already been done via the `docker-entry.sh`*

    kubectl exec -it $CWWED_POD python manage.py createcachetable

### Helpers

Collect covered data via job:

    emrichen --define deploy_stage=alpha --define tag=latest configs/job-collect-covered-data.in.yml | kubectl apply -f -

Manually run database migration:

    emrichen --define deploy_stage=alpha --define tag=latest configs/job-cwwed-migrate.in.yml | kubectl apply -f -
    
Patch to force a rolling update (to re-pull updated images):

    kubectl patch deployment cwwed-alpha -p "{\"spec\":{\"template\":{\"metadata\":{\"labels\":{\"date\":\"`date +'%s'`\"}}}}}"
    
Get pod name:

    CWWED_POD=$(kubectl get pods -l app=cwwed --no-headers -o custom-columns=:metadata.name)
    
Load demo data:

    kubectl exec -it $CWWED_POD python manage.py loaddata dev-db.json
    
Collect covered data by connecting directly to a pod:

    kubectl exec -it $CWWED_POD python manage.py collect_covered_data
    
Generate new api token for a user:

    kubectl exec -it ${CWWED_POD} -- python manage.py drf_create_token -r ${API_USER}
    
Connect to pod:

    kubectl exec -it $CWWED_POD bash
    
List all pods and the nodes they're on:

    kubectl get pod -o=custom-columns=NAME:.metadata.name,STATUS:.status.phase,NODE:.spec.nodeName --all-namespaces

Access OPENDaP behind CWWED's authenticated proxy

    import requests
    import xarray
    session = requests.Session()
    session.get('http://127.0.0.1:8000/accounts-login/')
    session.post('http://127.0.0.1:8000/accounts/login/', data={'login': 'XXX', 'password': 'XXX', 'csrfmiddlewaretoken': session.cookies.get('csrftoken')})
    store = xarray.backends.PydapDataStore.open('http://127.0.0.1:8000/opendap/PSA_demo/sandy.nc', session=session)
    dataset = xarray.open_dataset(store)

Delete PSAs:

    delete from named_storms_nsempsamanifestdataset where nsem_id = 59;
    delete from named_storms_nsempsauserexport where nsem_id = 59;
    delete from named_storms_nsempsacontour where nsem_psa_variable_id in (
        select id from named_storms_nsempsavariable where nsem_id = 59
    );
    delete from named_storms_nsempsadata where nsem_psa_variable_id in (
        select id from named_storms_nsempsavariable where nsem_id = 59
    );
    delete from named_storms_nsempsavariable where nsem_id = 59;
    delete from named_storms_nsempsa where id = 59;

### Celery dashboard (Flower)

- Go to the configured domain in Cloudflare
- Use the user/password saved in the secrets file when prompted via basic authorization

### Kubernetes Dashboard

[Dashboard UI](https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/#deploying-the-dashboard-ui):

Create kubernetes dashboard:

    kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.0.0-beta4/aio/deploy/recommended.yaml
    
Apply user/roles:

    kubectl apply -f configs/kube-service-account.yml
    kubectl apply -f configs/kube-cluster-role-binding.yml
    
Get token:

    kubectl -n kubernetes-dashboard describe secret $(kubectl -n kubernetes-dashboard get secret | grep admin-user | awk '{print $1}')

Start proxy:

    kubectl proxy

Dashboard URL: http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/

### Celery Flower

Celery's monitoring dashboard, Flower, isn't publicly exposed so you can port-forward locally like the following:

    kubectl port-forward celery-flower-deployment-644fd6d758-882nv 5556:5555

### Django Site

Configure a Django "Site" in admin so all messages refer to the appropriate server name and domain.

For example, log into the admin and create a site as `alpha.cwwed-staging.com`.

### Monitoring

#### CloudWatch > Container Insights

See [docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/deploy-container-insights-EKS.html).

Attach the *CloudWatchAgentServerPolicy* policy to all node's IAM roles.  There should be a *nodes* and *masters* role.

Find their IAM roles:

    aws iam list-roles | grep -E RoleName.*\(nodes\|masters\)

Attach policy to roles (**update role name accordingly**):

    aws iam attach-role-policy --role-name masters.cwwed-ingress-cluster.k8s.local --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy    
    aws iam attach-role-policy --role-name nodes.cwwed-ingress-cluster.k8s.local --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy    

Apply yaml for Cloudwatch agent for cluster metrics and Fluentd to send logs:

**NOTE: update the `cluster name` and `region` accordingly.**

    curl https://raw.githubusercontent.com/aws-samples/amazon-cloudwatch-container-insights/latest/k8s-deployment-manifest-templates/deployment-mode/daemonset/container-insights-monitoring/quickstart/cwagent-fluentd-quickstart.yaml | sed "s/{{cluster_name}}/cwwed-ingress-cluster.k8s.local/;s/{{region_name}}/us-east-1/" | kubectl apply -f -

View metrics at https://console.aws.amazon.com/cloudwatch/.

## NSEM S3 policies

Create AWS user *nsem* and assign the following polices:

- `configs/aws/s3-policy-nsem-shared.json` and they'll be able to upload to `s3://cwwed-shared/nsem/`.  See the [wiki instructions](https://github.com/CWWED/cwwed/wiki/NSEM-Shared-Storage-(AWS-S3))
- `configs/aws/s3-policy-nsem-upload.json` and they'll be able to read everything in `s3://cwwed-archives/NSEM/` and upload to `s3://cwwed-archives/NSEM/upload/`.

Create AWS user *cwwed-archives* and assign the following polices:

- `configs/aws/s3-policy-cwwed-archives.json` and they'll be able read/write `s3://cwwed-archives/`.

## CWWED User Exports lifecycle

Assign lifecycle for *User Exports* objects to expire after a certain amount of time.

    aws s3api put-bucket-lifecycle-configuration --bucket cwwed-archives --lifecycle-configuration file://configs/aws/s3-lifecycle-cwwed-archives.json

## Postgres table partitioning

CWWED keeps storm's granular data in separate partitions. One table per storm.

To create a new partition for a storm, see the [django-postgres-extra](https://django-postgres-extra.readthedocs.io/en/master/table_partitioning.html#adding-a-default-partition) docs.  

Basically you'll just create an empty migration and paste in something like this (see `named_storms/migrations/0120_auto_20220522_1953.py` for reference)

    ...
    operations = [
        PostgresAddListPartition(
           model_name="NsemPsaDataPartition",
           name="storm name",
           values=["STORM NAME"],
        ),
    ]
    ...
    
