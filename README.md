# Coastal Wind and Water Event Database (CWWED)

https://www.weather.gov/sti/coastalact_cwwed

[![Build Status](https://travis-ci.com/CWWED/cwwed.svg?branch=master)](https://travis-ci.com/CWWED/cwwed)

## Development & Initial Setup

### Python Environment (>=3.6)

    # create the python environment
    mkvirtualenv cwwed-env
    
    # install requirements
    pip install -r requirements.txt
    
    # activate environment when entering a new shell
    workon cwwed-env

### Running via Docker Compose
   
    # start PostGIS/OPeNDAP/RabbitMQ via Docker
    docker-compose up
    
    # start django server
    python manage.py runserver
    
    # start Celery and Flower (celery web management)
    python manage.py celery
    
### Initial Setup

    # migrate/create tables
    python manage.py migrate
    
    # create super user
    python manage.py createsuperuser
    
    # load dev data
    python manage.py loaddata dev-db.json

    # create "nsem" user & model permissions
    python manage.py cwwed-init
    
Collect Covered Data

    python manage.py collect_covered_data
    
### Build front-end app

    # copies output to a sub-folder which django includes as a "static" directory
    npm --prefix frontend run build-prod
    
### Helpers

Purge RabbitMQ

    docker-compose exec rabbitmq rabbitmqctl purge_queue celery
    
Purge Celery

    celery -A cwwed purge -f
    
Access OPENDaP behind CWWED's authenticated proxy

    import requests
    import xarray
    session = requests.Session()
    session.get('http://127.0.0.1:8000/accounts-login/')
    session.post('http://127.0.0.1:8000/accounts/login/', data={'login': 'XXX', 'password': 'XXX', 'csrfmiddlewaretoken': session.cookies.get('csrftoken')})
    store = xarray.backends.PydapDataStore.open('http://127.0.0.1:8000/opendap/PSA_demo/sandy.nc', session=session)
    dataset = xarray.open_dataset(store)
    
Dump Postgres table(s)

    # local: data only, specific tables
    docker-compose exec postgis pg_dump -a -h localhost -U postgres -d postgres -t named_storms_nsempsavariable -t named_storms_nsempsadata > ~/Desktop/cwwed.sql
    
Connect to remote Postgres:

    docker-compose exec postgis psql -h XXX.rds.amazonaws.com -U XXX cwwed_dev
    
    
## Production
    
### Create Kubernetes cluster

Create Kubernetes cluster via [kops](https://github.com/kubernetes/kops).

    # create cluster (dev)
    kops create cluster --master-count 1 --node-count 2 --master-size t2.medium --node-size t2.medium --zones us-east-1a --name cwwed-dev-ingress-cluster.k8s.local --state=s3://cwwed-kops-state --yes
    
    # (if necessary) configure kubectl environment to point at aws cluster
    kops export kubecfg --name cwwed-dev-ingress-cluster.k8s.local --state=s3://cwwed-kops-state

#### Setup RDS (relational database service) with proper VPC (from cluster) and security group permissions.

Do this in the AWS Console.
    
#### Create EFS
Create EFS (elastic file system) in console and **make sure** it's in the same region, VPC and security group as the cluster.

efs-provisioner: https://github.com/kubernetes-incubator/external-storage/tree/master/aws/efs
**NOTE** I had to modify yaml settings via github issues: [1](https://github.com/kubernetes-incubator/external-storage/issues/1209), [2](https://github.com/kubernetes-incubator/external-storage/issues/953)

Copy the `File System Id` from the new efs instance and update `configs/manifest.yml` accordingly.

Create kubernetes persistent volume & claim with the new efs instance:
    
    # create efs volume (can take a couple minutes to create the provisioner pod)
    kubectl apply -f configs/aws-efs/rbac.yaml
    kubectl apply -f configs/aws-efs/manifest.yaml
    
### Nginx Ingress

User nginx as the kubernetes ingress.

https://kubernetes.github.io/ingress-nginx/

    kubectl apply -f configs/nginx-ingress/mandatory.yml
    kubectl apply -f configs/nginx-ingress/service-14.yml
    kubectl apply -f configs/nginx-ingress/patch-configmap-14.yml
    
##### Load Balancing

The nginx ingress will automatically create a AWS Load Balancer.
Once the nginx ingress service is created,
monitor the new external Load Balancer and get it's external IP address.

    kubectl get service --namespace ingress-nginx ingress-nginx
    
Use that IP and configure DNS via Cloudflare.
    
### Secrets
    
    # create secrets using proper stage
    # update $DEPLOY_STAGE to "dev", "alpha" etc
    DEPLOY_STAGE=alpha
    # NOTE: always create new secrets with `echo -n "SECRET"` to avoid newline characters
    # NOTE: when updating, you need to either patch it (https://stackoverflow.com/a/45881259) or delete & recreate: `kubectl delete secret cwwed-secrets-$DEPLOY_STAGE`
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

### Install all the services, volumes, deployments etc.

For yaml templates, us [emrichen](https://github.com/con2/emrichen) to generate yaml and pipe to `kubectl`.

For instance, deploy cwwed by defining the *deploy_stage* and cwwed image *tag*:

    # alpha => latest
    emrichen --define deploy_stage=alpha --define tag=latest configs/deployment-cwwed.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha --define tag=latest configs/service-cwwed.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha --define tag=latest configs/deployment-celery.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha configs/deployment-opendap.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha configs/service-opendap.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha configs/deployment-rabbitmq.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=alpha configs/service-rabbitmq.in.yml | kubectl apply -f -

    # dev => v1.0
    emrichen --define deploy_stage=dev --define tag=v1.0 configs/deployment-cwwed.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev --define tag=v1.0 configs/service-cwwed.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev --define tag=v1.0 configs/deployment-celery.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev configs/deployment-opendap.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev configs/service-opendap.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev configs/deployment-rabbitmq.in.yml | kubectl apply -f -
    emrichen --define deploy_stage=dev configs/service-rabbitmq.in.yml | kubectl apply -f -
    
    
**OPTIONAL** define yaml templates for the following:

    kubectl apply -f configs/deployment-celery-flower.yml
    kubectl apply -f configs/service-celery-flower.yml
   
Everything else:

    # ingress
    kubectl apply -f configs/ingress.yml
    
    # patch the persistent volume to "retain" rather than delete if the claim is deleted
    # https://kubernetes.io/docs/tasks/administer-cluster/change-pv-reclaim-policy/
    kubectl patch pv XXX -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
    
### Initializations

Create the default super user:

    kubectl exec -it $CWWED_POD python manage.py createsuperuser
    
Run initializations like creating the "nsem" user and assigning permissions:

    kubectl exec -it $CWWED_POD python manage.py cwwed-init
    
Create cache tables:

*This should have already been done via the `docker-entry.sh`*

    kubectl exec -it $CWWED_POD python manage.py createcachetable
    
### Helpers
    
    # collect covered data via job
    kubectl apply -f configs/job-collect-covered-data.yml
    
    # patch to force a rolling update (to re-pull images)
    kubectl patch deployment cwwed-deployment -p "{\"spec\":{\"template\":{\"metadata\":{\"labels\":{\"date\":\"`date +'%s'`\"}}}}}"
    
    # get pod name
    CWWED_POD=$(kubectl get pods -l app=cwwed --no-headers -o custom-columns=:metadata.name)
    
    # load demo data
    kubectl exec -it $CWWED_POD python manage.py loaddata dev-db.json
    
    # collect covered data by connecting directly to a pod
    kubectl exec -it $CWWED_POD python manage.py collect_covered_data
    
    # generate new api token for a user
    kubectl exec -it ${CWWED_POD} -- python manage.py drf_create_token -r ${API_USER}
    
    # connect to pod
    kubectl exec -it $CWWED_POD bash
    
### Celery dashboard (Flower)

    - Go to the configured domain in Cloudflare
    - Use the user/password saved in the secrets file when prompted via basic authorization
   
### Kubernetes Dashboard

[Dashboard UI](https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/#deploying-the-dashboard-ui):
    
    # create kubernetes dashboard
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.0.0-beta4/aio/deploy/recommended.yaml
    
    # apply user/roles
    kubectl apply -f configs/kube-service-account.yml
    kubectl apply -f configs/kube-cluster-role-binding.yml
    
    # get token
    kubectl -n kubernetes-dashboard describe secret $(kubectl -n kubernetes-dashboard get secret | grep admin-user | awk '{print $1}')

    # start proxy
    kubectl proxy
    
Dashboard URL: http://localhost:8001/api/v1/namespaces/kube-system/services/https:kubernetes-dashboard:/proxy/#!/overview?namespace=default
    
### Celery Flower

Celery's monitoring dashboard, Flower, isn't publicly exposed so you can port-forward locally like the following:

    kubectl port-forward celery-flower-deployment-644fd6d758-882nv 5556:5555
    
### Social auth

**TODO**

Configure Django "Sites" (in admin)

    For example, log into the admin and create a site as `dev.cwwed-staging.com`.
    
### Monitoring

*NOTE: This takes up a lot of resources and is not in use.*

Monitoring via Prometheus/Grafana.
[Install](https://github.com/coreos/prometheus-operator/tree/master/contrib/kube-prometheus) by checking out repository and applying the included manifests.

User:admin

    # port forward grafana to local
    kubectl port-forward $(kubectl get pods -l app=grafana -n monitoring --output=jsonpath="{.items..metadata.name}") -n monitoring 3000

    
## NSEM process

Create a new Covered Data Snapshot:

    curl -s -H "content-type: application/json" -H "Authorization: Token eedcd6961d8bb2b28da8643c16c24eb7af035783" -d '{"named_storm": 1}' http://127.0.0.1:8000/api/named-storm-covered-data-snapshot/
   
This creates the snapshot in the background and emails the 'nsem' user once complete.  Retrieve the id.
    
Download the covered data snapshot (say, id=1):

    aws s3 cp --recursive "s3://cwwed-archives/NSEM/Harvey/Covered Data Snapshots/1/" /YOUR/OUTPUT/PATH --profile nsem
    
Upload PSA to S3 object storage:

*NOTE:* The input format must be tar+gzipped and named the correct version, i.e "psa.tgz".
    
    # upload using checksum
    FILE="psa.tgz"
    UPLOAD_PATH="NSEM/upload/psa.tgz"
    CHECKSUM=$(openssl md5 -binary "${FILE}" | base64)
    aws s3api put-object --bucket cwwed-archives --key "${UPLOAD_PATH}" --body "${FILE}" --metadata md5chksum=${CHECKSUM} --content-md5 ${CHECKSUM} --profile nsem

Create a new PSA record to begin the extraction, validation and ingest:

    curl -s -H "content-type: application/json" -H "Authorization: Token eedcd6961d8bb2b28da8643c16c24eb7af035783" -d@samples/psa-create.json http://127.0.0.1:8000/api/nsem-psa/ | python -mjson.tool

## NSEM AWS policies

Create AWS user *nsem* and assign the following polices:

 - `configs/aws/s3-policy-nsem-shared.json` and they'll be able to upload to `s3://cwwed-shared/nsem/`.  See the [wiki instructions](https://github.com/CWWED/cwwed/wiki/NSEM-Shared-Storage-(AWS-S3))
 - `configs/aws/s3-policy-nsem-upload.json` and they'll be able to read everything in `s3://cwwed-archives/NSEM/` and upload to `s3://cwwed-archives/NSEM/upload/`.
    
Create AWS user *cwwed-archives* and assign the following polices:
 
 - `configs/aws/s3-policy-cwwed-archives.json` and they'll be able read/write `s3://cwwed-archives/`.
 
## CWWED User Exports lifecycle
 
Assign lifecycle for *User Exports* objects to expire after a certain amount of time. 

    aws s3api put-bucket-lifecycle-configuration --bucket cwwed-archives --lifecycle-configuration file://configs/aws/s3-lifecycle-cwwed-archives.json
