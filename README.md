# Coastal Wind and Water Event Database (CWWED)

https://www.weather.gov/sti/coastalact_cwwed

## Development & Initial Setup

### Python Environment (>=3.6)

    # create the python environment
    mkvirtualenv cwwed-env
    
    # install requirements
    pip install -r requirements.txt
    
    # activate environment if in a new shell
    workon cwwed-env

### Running via Docker Compose
   
    # start PostGIS/THREDDS/RabbitMQ via Docker
    docker-compose up
    
    # start server
    python manage.py runserver
    
    # start Celery and Flower (celery web management)
    python manage.py celery
    
Initial Setup

    # migrate/create tables
    python manage.py migrate
    
    # create super user
    python manage.py createsuperuser
    
    # load dev data
    python manage.py loaddata dev-db.json

    # create "nsem" user & model permissions
    python manage.py cwwed-init
    
##### Helpers

Purge RabbitMQ

    docker-compose exec rabbitmq rabbitmqctl purge_queue celery
    
Purge Celery

    celery -A cwwed purge
    
    
### Running via Kubernetes

Using [Minikube](https://github.com/kubernetes/minikube) for local cluster.

    # start cluster in vm
    # NOTE: this automatically configures the docker & kubectl environments to point to the minikube cluster
    minikube start --memory 8192
    
    # run if you want the docker & kubectl environments in a different terminal
    eval $(minikube docker-env)
    kubectl config use-context minikube
    
    # build images
    docker build -t cwwed-app .
    docker build -t cwwed-thredds configs/thredds
    
    # create secrets
    kubectl create secret generic cwwed-secrets --from-literal=CWWED_NSEM_PASSWORD=$(cat ~/Documents/cwwed/secrets/cwwed_nsem_password.txt) --from-literal=SECRET_KEY=$(cat ~/Documents/cwwed/secrets/secret_key.txt) --from-literal=SLACK_BOT_TOKEN=$(cat ~/Documents/cwwed/secrets/slack_bot_token.txt) --from-literal=DATABASE_URL=$(cat ~/Documents/cwwed/secrets/database_url.txt)
    
    # create everything all at once (in the right order: services, local volumes then deployments)
    ls -1 configs/local_service-*.yml configs/service-*.yml configs/local_volume-* configs/local_deployment-* configs/deployment-* | xargs -L 1 kubectl apply -f
    
    # delete everything
    ls -1 configs/*.yml | xargs -L 1 kubectl delete -f
    
    # create services individually
    kubectl apply -f configs/service-cwwed.yml
    kubectl apply -f configs/local_service-postgis.yml
    kubectl apply -f configs/service-thredds.yml
    kubectl apply -f configs/service-rabbitmq.yml
    kubectl apply -f configs/service-celery-flower.yml
    
    # create volumes individually
    kubectl apply -f configs/local_volume-cwwed.yml
    kubectl apply -f configs/local_volume-postgis.yml
    
    # create deployments individually
    kubectl apply -f configs/deployment-cwwed.yml
    kubectl apply -f configs/deployment-thredds.yml
    kubectl apply -f configs/deployment-rabbitmq.yml
    kubectl apply -f configs/deployment-celery.yml
    kubectl apply -f configs/deployment-celery-flower.yml
    kubectl apply -f configs/local_deployment-postgis.yml
    
    # get pod name
    CWWED_POD=$(kubectl get pods -l app=cwwed-container --no-headers -o custom-columns=:metadata.name)
    
    # connect to pod
    kubectl exec -it $CWWED_POD bash
    
    # initializations
    kubectl exec -it $CWWED_POD python manage.py migrate
    kubectl exec -it $CWWED_POD python manage.py createsuperuser
    kubectl exec -it $CWWED_POD python manage.py cwwed-init
    kubectl exec -it $CWWED_POD python manage.py loaddata dev-db.json
    
    # collect covered data
    kubectl exec -it $CWWED_POD python manage.py collect_covered_data
    
    # get minikube/vm cwwed url
    minikube service cwwed-app-service --url
    
    # get minikube/vm celery/flower url
    minikube service celery-flower-service --url
    
    # delete minikube cluster
    minikube delete
    
    
## Production *-TODO-*
Setup RDS with proper VPC and security group permissions.

EFS:
- Create EFS instance
- Assign EFS security group to EC2 instance(s).  (TODO - figure out how auto scaling default security groups work)

Environment variables
- `SECRET_KEY`
- `DJANGO_SETTINGS_MODULE`
- `DATABASE_URL`
- `SLACK_BOT_TOKEN`
- `CWWED_NSEM_PASSWORD`
- `AWS_STORAGE_BUCKET_NAME`

Create S3 bucket and configure CORS settings (prepopulated settings look ok).
However, `django-storages` might configure it for us with the setting `AWS_AUTO_CREATE_BUCKET`.

    # collect static files to S3 (from local/dev computer since it's auth'd with aws)
    AWS_STORAGE_BUCKET_NAME=cwwed-static-assets python manage.py collectstatic --settings=cwwed.settings_aws
    
    # create cluster (dev)
    kops create cluster --master-count 1 --node-count 1 --master-size t2.medium --node-size t2.micro --zones us-east-1a --name cwwed-dev-cluster.k8s.local --state=s3://cwwed-kops-state --yes
    
    # configure kubectl environment to point at aws cluster
    kops export kubecfg --name cwwed-dev-cluster.k8s.local --state=s3://cwwed-kops-state
    
    # create EFS and make sure it's in the same VPC as the cluster, along with the node's security group
    
    # patch the persistent volume to "retain" rather than delete if the claim is deleted
    # https://kubernetes.io/docs/tasks/administer-cluster/change-pv-reclaim-policy/
    kubectl patch pv XXX -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
    
    # collect covered data via job
    kubectl apply -f configs/job_collect-covered-data.yml
    
    # force a rolling update (to repull images)
    kubectl patch deployment cwwed-deployment -p "{\"spec\":{\"template\":{\"metadata\":{\"labels\":{\"date\":\"`date +'%s'`\"}}}}}"
   
Kubernetes Dashboard
    
    # create kubernetes dashboard
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/master/src/deploy/recommended/kubernetes-dashboard.yaml
    
    # apply user/roles
    kubectl apply -f configs/kube-service-account.yml
    kubectl apply -f configs/kube-cluster-role-binding.yml
    
    # get token
    kubectl -n kube-system describe secret $(kubectl -n kube-system get secret | grep admin | awk '{print $1}')
    
    # start proxy
    kubectl proxy

    
## NSEM process

Submit a new NSEM request using the user's generated token:

    curl -H "Authorization: Token aca89a70c8fa67144109b368b2b9994241bdbf2c" -H "Content-Type: application/json" -d '{"named_storm": "1"}' http://127.0.0.1:8000/api/nsem/
    
    {
        "id": 45,
        "covered_data_snapshot_url": "http://127.0.0.1:8000/api/nsem/43/covered-data/",
        "date_requested": "2018-04-04T14:28:00.646771Z",
        "date_returned": null,
        "covered_data_snapshot": "/media/bucket/cwwed/Harvey/NSEM/v43/input.tar",
        "model_output_snapshot": "",
        "named_storm": 1
    }

    
Download the covered data for an NSEM record:

    curl -s -H "Authorization: Token aca89a70c8fa67144109b368b2b9994241bdbf2c" http://127.0.0.1:8000/api/nsem/45/covered-data/ > /tmp/data.tgz
    
Upload model output for a specific NSEM record:

*NOTE: The input format must be tar+gzipped, i.e "output.tgz".*

    # assumes "output.tgz" is in current directory
    curl -XPUT -H "Authorization: Token aca89a70c8fa67144109b368b2b9994241bdbf2c" --data-binary @output.tgz "http://127.0.0.1:8000/api/nsem/45/upload-output/"
