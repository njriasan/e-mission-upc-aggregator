# E-MISSION User Private Clouds

This repository contains the implementation of User Private Clouds (UPC) and the relevant services used to operate select e-mission functionality within UPC. A higher level description of UPC is available in my [technical report](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2020/EECS-2020-130.html).

## Installation
To get everything to work properly with the current implementation, you need at least one linux machine with the following installations:

* Anaconda Python3
* Ecryptfs
* Docker
* Either docker-compose or kubernetes

### Anaconda Python3
On each machine we need a host process to provision docker instances which means you need access to `Python 3.5` or greater. Depending on the data analysis you wish to run you may need access to additional libraries, most of which should be supported by the `conda env` produced for the base e-mission server. You find the installation instructions [here](https://github.com/e-mission/e-mission-docs/blob/master/docs/install/manual_install.md).

### Ecryptfs

If you are planning on using or testing encrypted storage at rest you will need to run on a linux platform that can install `Ecryptfs`. This can be installed directly through `apt` on `Ubuntu`: 
```
$: sudo apt-get update
$: sudo apt-get install ecryptfs-utils
```
If you do not have a Linux distribution or your version of Linux does not support `Ecryptfs` then you will be unable to encrypt the storage and modifications will need to be made to prevent the existing implementation from crashing. 

We opted to use `Ecryptfs` mainly because it was easy to use and its encryption can be accomplished through mount commands. This does require that the containers are run with increased permissions however.

### Docker

Having `docker` is essential to running the modified architecture because every single component runs inside a container except for the component responsible for launching containers. You can find information on how to install `docker` on your platform from their [website](https://docs.docker.com/install/), as well as information on how `docker` works if you are unfamiliar.

### Docker-Compose or Kubernetes

Our current implementation supports either using docker-compose with a set of servers we built or kubernetes to launch the UPC services. There are tradeoffs with each selection, which hopefully these will do a good job of summarizing. We cannot use docker-swarm because ecryptfs requires sudo permissions, which are not available with docker-swarm.

Docker-Compose Advantages:
    * Simple to use.
    * Pausing containers is possible. This is useful if you need many concurrent users.
    * Each container is very lightweight.
    
Docker-Compose Disadvantages:
    * Not representative of a real system.
    * No native distributed storage.
    * Currently no support for recovery upon whole machine failure.
    * Server upkeep cannot no longer be a cloud task.
    * Less isolation than Kubernetes offers.

Kubernetes Advantages:
    * Designed to balance pods across machines.
    * Easy configuration on cloud machines.
    * Recovery upon machine failure
    * Better able to set resource limits.
    * Overall more development.

Kubernetes Disadvantages:
    * Pods are a bad fundamental layer and the number of pods that can be spawned at once is very small. You may need to get creative with how you reuse pods.
    * No support for pausing containers.
    * Constructing a Kubernetes cluster may be more difficult than just installing docker.
    * Kubernetes has a harsher learning curve because it has more functionality.

Ultimately I would suggest using Kubernetes. However, if you need many concurrent users for deployment you will need to decide how to allocate users (it will be far too slow to delete pods as needed) and you may need to pick the best way to recycle containers. If this proves too difficult and pausing containers is essential to usable performance, then you may need to settle for the docker-compose based implementation.

#### Installing Docker-Compose

You can find the documentation on `docker-compose` and how to install it on this [website](https://docs.docker.com/compose/install/). 

#### Installing Kubernetes

To run kubernetes there are a few necessary components. First you must install [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) and its dependencies on at least one machine, whichever machine hosts the service router. Next you will need access to a Kubernetes cluster. For testing purposes you will probably first want to install [minikube](https://kubernetes.io/docs/tasks/tools/install-minikube/). Minikube containers can interact with each other so you can test correctness with a single machine. You may also need to configure your docker images to work properly with minikube, either by uploading the images to a remote registry from which minikube will download or by [building the images directly in minikube](https://stackoverflow.com/questions/52310599/what-does-minikube-docker-env-mean). 

While it may be possible to run multi-machine cluster using minikube, I am not familiar with how to do so. Instead I recommend using a cloud provider that has kubernetes support. In my technical report I found the [Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine) particularly easy to use and if you are a student you may have free credits. However when transitioning to a cloud kubernetes engine you may have to make additional changes to adhere to requirements of the cloud provider. For example, in my experience I needed to change all of the docker images paths to correspond to Google's [container registry](https://cloud.google.com/container-registry), and I needed to modify the firewall rules to allow external traffic to access the ports the containers would occupy (because we use the NodePort service type).

## Architecture Code

To facilitate our new architecture we have added new code and docker functionality in a variety of locations. Regretably these are probably not the best locations to place this code and our changes can seem a bit disjoint in their placement. I will do my best to list what is located where and what its purpose is. Additionally with each section we will present a brief higher level overview of the intended purpose of each component, but this is not meant asa substitute for a detailed description of the architecture (which is in progress).

However before we can detail the exact component we need an overview of the components. Our new architecture basically consists of 3 components:

1. Users
2. Algorithm Providers
3. A system controller

These components are then split further into various subcomponents but at a very high level users provide their data and have an abstraction of an individualized workstation through our "user cloud" abstraction. Algorithm providers interact directly which each user to acquire their necessary data and then aggregate their results as necessary. The system controller is responsible for providing the connection between users and their storage as well as algorithm providers access to users. By abstracting this component into a controller it allows us to dynamically reallocate resources.

### System Controller

The system controller is basically a central server that all participants connect to. It can perform a variety of tasks, some of which are:

* Tell an algorithm instance where to find users.
* Tell users where their user cloud is located.
* Create a user cloud for a newly signed up user.
* Pause and unpause the physical container for each cloud.

The last task is particularly important to us because our focus on placing everything in containers for increased isolation relies on an assumption that most of time each user cloud will not be processing data. This allows us to pause that instance which makes us better capable to provision our CPU resources more effectively (presumably at some cost to storing on disk).

Our actually implementation of this involves using `bottle.py` to create a server that receives post requests at some known address. Then our server holds mappings of users to their clouds locations as well as their current status ("Running" or "Paused"). Finally the server will periodically pause containers not in use according to some user specified timing requirements.

#### Files
The actually files changed or added to implement the controller (relative to the e-mission-server base directory) are:

* `launch_machine.py` - Helper script to launch the controller.
* `conf/net/machines.json.sample` - Example configuration used to specify the controller
* `emission/net/api/controller.py` - Actual code used to provide the server.

We also interact with existing e-mission files as well as some possible helper scripts but we will not detail them here.

### User Data Storage

User data storage is done through our "user cloud" concept. The user cloud is currently simply a copy of the e-mission server but with extra information (for example the ability to send the user's key to mongo to deploy the database over an encrypted file system). For this reason we have opted to included all the original e-mission code with some extra functionality. This conseqeuentially means that code sizes are a lot bigger than should be necessary (because we include a lot of files we didn't modify) and we haven't removed any of the code that is no longer relevant (for example each user still needs to log in and register despite being the only user in the container. There should be a more modular approach that would for example allow us to only swap in the `cfc_webapp.py` file into an existing docker image that otherwise contains the rest of the e-mission code but we have not looked into doing this. 

The presence of additional user clouds per machine also required us to provision ports dynamically and present that information through environment variables (to make each instance unique from the same start script). This is NOT a robust process and understanding the exact rules for naming likely requires further investigation.

#### Files
The actually files changed or added to implement the user cloud (relative to the e-mission-server base directory) are:

* `emission/net/api/cfc_webapp.py` - Actual code for the e-mission web server. You can find my changes in a section commented "Nick's changes"

We also interact with existing e-mission files as well as some possible helper scripts but we will not detail them here.

### Data Simulation

Data simulation is almost entirely consistent with the main branch of the e-mission server. We use the same fake data generator and we have only modified the example script that generates user data to support our examples. This was primarily done by moving the code from `Data Generator - Demo.ipyn` to `initialize_data.py` so that it could run without `iPython notebook`.

Additionally we opted to modify the example to deterministically alternate between two fixed locations (so that we could have a consistent and fixed amount of data). This may or may not be a useful method moving forward.

### Data Aggregation

In implementing algorithms we opted to split algorithms into 2 components:

1. An aggregation component that process the whole dataset.
2. A set of queriers that collect data from users one at a time, possibly with one querier per user.

Our primary example use case was `Jack Sullivan's` work on differentially private queriers, which is why we opted to struct code in this manner. You can find the relevant code in many locations, but we opted to stick with the same `POST Request` server model for all components (i.e. a research launches an aggregator server which gets many queriers launched through the controller). We currently only use functionality that we added (for example to support being able to ask if data exists for a particular range and if so to retrieve it). We have not shown any support for an aggregator that for example wants to run the e-mission pipeline on some subset of users. We also do not have any work on modifying how users are requested/sampled and how to ensure it is done in a fair process.

#### Files
The actually files used to implement aggregation (relative to the e-mission-server base directory) are:

* `emission/net/ext_service/launch_aggregator.py` - Helper script to launch the sample aggregator.
* `emission/net/ext_service/aggregator.py` - Actual code for the server component of the sample aggregator.

We also interact with existing e-mission files as well as some possible helper scripts but we will not detail them here.

### Data Querying

The data querying component is an additional POST server. This component is far more in tune with a traditional microservices architecture as all instances are identical except for the endpoints at which they connect. For that reason a feasible redesign would be to just deploy the queriers in a standard kubernetes cluster. The actual functionality is that the controller spawns each querier instance and then provides the aggregator with addresses of the queriers. Then the aggregator connects with the querier and provides a set of users that it wants the querier to connect to and the querier will then performed that request by making a post request to the desired user clouds. Finally it send the result to the aggregator (and if necessary remains up to execute any concluding interaction with the usercloud).

#### Files
The actually files used to implement the querier (relative to the e-mission-server base directory) are:

* `runQueryCorrect.py` - Helper script to launch a correctness query.
* `emission/net/int_service/query_microservice.py` - Sample implementation of a querier server.

We also interact with existing e-mission files as well as some possible helper scripts but we will not detail them here.

### Multimachine Communication

One fundamental challenge with this project was the struggle to align the project with existing schema in microservices architectures. To illustrate this more clearly let's give the example of how `kubernetes` or `docker swarm` might opt to handle a web server. The general paradigm is that someone creates an image of the web server. The user does this with some number of instances to reflect their expected workload. However all users connect to the same web address and `kubernetes` decides which web server should be routed traffic based on load management, similarly managing the movement of instances across a cluster of machines. Crucially all web traffic goes to the same place because all instances are identical! In our user cloud implementation we have a code base which should be identical for each user but once a user connects it is no longer stateless, so a user must connect again to the previous instance it connected to (the only piece of state we have added is a user secret key to encrypt data but this is a very important piece of state).

The implication of this is that we cannot treat the user cloud as a service in the way a traditional microservices architecture would and instead need to create individual containers manually. Due to limitations in `docker swarm` we actually can't even directly deploy containers as services with a single container (it cannot provide privleged containers). This is not a limitation with `kubernetes`, which makes it promising as an alternative, especially given that kubernetes can then address issues like load management and reliability. However we have opted to push this to future work, mostly because there are not many theoretical challenges with using `kubernetes` but I was unexperienced and my research seemed to indicate setup can be complex. One definite improvement would be to port these modules to `kubernetes` and hopefully in the process remove many of the hacks needed to implement it.

For the time being we using docker to spawn individual contains and associate machines together with many a per machine python server that can launch a docker container. We then decide how to allocate containers across machines using static information (though we could use information like current CPU consumed and available memory but we figured this was a temporary fix before using kubernetes).

#### Files
The actually files used to implement the controller (relative to the e-mission-server base directory) are:

* `conf/net/machines.json.sample` - Example configuration used to specify machines that can be accessed. It does not provide support for fault tolerance for example.
* `emission/net/int_service/swarm.py` - Server run locally to actually launch docker commands. This should be removed eventually.
* `emission/net/int_service/swarm_controller.py` - Helper file to provide abstractions to the controller about how to launch an instance. This should be removed eventually.

We also interact with existing e-mission files as well as some possible helper scripts but we will not detail them here.

### Docker Changes

You can find information about how to run the code in `docker/README.md`. One important piece of information is that testing any changes requires pushing to github (and likely requires that you modify the docker file and relevant start scripts to reflect that endpoint). The reason is that the existing code base creates the docker image by executing `git clone` when building the image. We made further modifications by having the start script pull the latest commit to avoid rebuilding the image, but all of this indicates that testing changes require pushing to a remote repository.

You can find the details on how constructing the docker instances work in the `docker/README.md` as well.

### Reading the Code

To get familiar with our implementation and changes we suggest the following reading order:

1. Multimachine Communication - This should consist mostly of raw docker commands so hopefully it gives a clear picture of what is actual happening.
2. `bottle.py` - Reading and understanding how a bottle server works is the next step for understanding what the controller and user cloud are based around.
3. `controller.py` and `cfc_webapp.py` - Together these should give an overview of how the controller and user cloud actually exist. It should also highlight what is happening inside containers.
4. Data generation scripts - Both how to call them and what is happening should provide an understanding of how to actually fill a user cloud.
5. Data Aggregator and Data Querier - These together should provide an example of how an application may query and interact with our user cloud
6. Scripts to run the whole process (`runNewArch.py` for example) - These should give you an example how use can construct experiments to test the architecture.

## Running an Example

First you need to make sure the relevant docker images are built. This information can be found in `docker/README.md` and for our example this will require building all 3 of the images listed. If you are planning on using this as a starting point for future changes there a couple important takeaways.

1. If you want your changes to be reflected and you are not working off the main branch you need to modify all 3 dockerfiles and change possibly the repository name and the branch. Failure to do so will cause the image to fail to download your changes from github.
2. Any changes that you make must be pushed to github to test them. This is necessary because again the image downloads from your repository. It is however not necessary to rebuild the images each time you make a change because we have added commands into the startup script to download the latest commit (which you also be aware of in case you want to control which components have up to date changes and which do not). For this reason we recommend using multiple branches and if you are planning on making large changes possibly a different branch for each component so you can test them independently.

Once you actually begin making changes and have configured your repository and branches future builds can be completed from the `build_images.sh` script.

Next you need to make sure and update what machines you will be using. Eventually this step should be replaced by configuring your kubernetes cluster. However since that functionality is not yet available and our configuration is not compatible with docker swarm due to its reliance on privileged containers, you will need to modify our configuration for our docker "controller." To do so you want to open the file `conf/net/machines.json.sample`. In this file you will find a few important json fields. Most of these you won't need to edit (and you should refer to the code if you are curious about their functionality) but you may need to change `controller-ip`, which refers to the ip address from which you will launch your controller, `controller-port` which is the public accessible tcp port upon which the controller will run, `swarm-port` which is the port from which a per machine server responsible for launching docker containers will run, and finally `machines` which is a dictionary mapping ip addresses of the machines participating to integer values. These integers don't necessarily have any inherent meaning but can be used if you want to give weighted priority to certain machines when launching UPC containers based upon their features (for example available RAM).

Now that you have completed the necessary setup you need to launch the server that will spawn docker containers across your machines. This requires you to first launch the e-mission anaconda environment as the server must be run outside of docker so they can eventually launch docker containers. Assuming you have already setup the installation steps for the anaconda environment found [here](https://github.com/e-mission/e-mission-docs/blob/master/docs/install/manual_install.md) run:
```
 $ source setup/setup.sh
```

You must do this on every machine you will be using (and if you plan on using more than one terminal in each terminal you use). Now from inside the e-mission environment you can launch the server and controller. To do so run

```
 $ ./e-mission-py.bash launch_machine.py
```

 The script `launch_machine.py` will setup the controller if the ip address matches the controller and launch the server (note this will takeup one terminal). If you need greater inspect you can launch each component manually in a separate terminal (check the script for details). This means its also very important that you push your configuration file to your repository and ensure it is consistent across all machines participating. If this script is not launching the controller check that the ip address matches the form expected by the script and that ip address matches the ip address python receives when it calls `gethostbyname` on the current machine.

Finally once your network is started (which may take a while on the first attempt) you can run any of your tests. In this example we will run `runNewArch.py`, which creates fake users, uploads their data to each UPC and finally particpates in some queries. To launch this you can run

```
 $ ./e-mission-py.bash runNewArch.py
```

from a terminal in the e-mission source environment. This example may take a while before you see any output. If you are seeking to make your own trials then consider investigating this script and the more importantly the scripts it calls in order to function. 

### Teardown

One issue you may encounter is that if you are running tests you can accidentally dedicate a lot of memory to stopped docker containers. To address this we offer two nearly identical scripts. `prune_docker.sh` will prune any docker images, volumes, or containers you have that are not being used but are consuming memory. `teardown_docker.sh` does the same thing but also first stops all currently running docker containers (which means you should be very careful if you have other docker containers running on your machine.


### Summary

In conclusion the steps to running an example in UPC are 

1. Build the images, first by modifying the dockerfiles to refer to your repository and then using `build_images.sh`.
2. Update the configuration file, `/conf/net/machines.json.sample` to refer to the machines you will be using.
3. Load the e-mission environment.
4. Launch the server on each machine and the controller on the dedicated machine with `launch_machine.py`.
5. Run your desired test file, such as `runNewArch.py`
6. Teardown as necessary or desired with either `prune_docker.sh` or `teardown_docker.sh`
