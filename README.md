webcompat-search
=======================

Description
-------------
Web service to expose HTTP API that allows searching webcompat issues based on:

* flask
* elasticsearch

Initial configuration
------------------------
We scrape github issues using Github API which requires a token for authentication.
Get a personal access token following the instructions [here](https://bit.ly/2OVfzXR).

Then setup the configuration using the following commands (in the toplevel of the project):

```
$ touch .env
$ echo "GITHUB_API_TOKEN = <GITHUB_API_TOKEN>" >> .env
```

You also need to install `docker` and `docker-compose`.

* [docker](https://docs.docker.com/install/)
* [docker-compose](https://docs.docker.com/compose/)

Building
---------

* `docker-compose pull` to pull the dependent images
* `docker-compose build` to build the image for the service

Getting started
------------------

To populate ES with issues

* `docker-compose run --service-ports flask fetch_issues --state=open`

To run the web service:

* `docker-compose build`
* `docker-compose up`
