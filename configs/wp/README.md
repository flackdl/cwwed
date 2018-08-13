## WordPress

This installation expects an accessible MySQL/MariaDB instance at `WORDPRESS_DB_HOST`.

The `/var/www/html` directory is mounted to EFS so all file system changes (i.e themes) are persistent.

    # create secrets
    kubectl create secret generic wp-secrets --from-literal=WORDPRESS_DB_HOST=$(cat ~/Documents/cwwed/secrets/wp-host.txt) --from-literal=WORDPRESS_DB_PASSWORD=$(cat ~/Documents/cwwed/secrets/wp-password.txt)
    
    # create service
    kubectl apply -f configs/service-wordpress.yml
    
    # create deployment
    kubectl apply -f configs/deployment-wordpress.yml
    
    # alter php settings by modifying the `.htaccess` file in the mounted `/var/www/html` directory
    php_value upload_max_filesize 64M
    php_value post_max_size 64M
