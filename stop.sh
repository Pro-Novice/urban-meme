./deploy.sh stop
docker kill $(docker ps -aq)
docker rm $(docker ps -aq)
dockert network prune
