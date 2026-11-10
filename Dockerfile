FROM ros:jazzy-ros-base-noble@sha256:c26c86a28e1addf9d10a81232869791974a3f7907943d5634742b58b2f26e1a3
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install --no-install-recommends -y \
    ros-jazzy-turtlebot4-simulator \
    ros-jazzy-irobot-create-nodes \
    ros-jazzy-cv-bridge \
    ros-jazzy-image-transport \
    ros-jazzy-vision-msgs \
    python3-colcon-common-extensions \
    python3 python3-numpy python3-opencv python3-pytest \
    build-essential git cmake curl ca-certificates libcurl4-openssl-dev \
    xvfb xauth mesa-utils libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*
ENV ROS_DOMAIN_ID=84 \
    ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    LIBGL_ALWAYS_SOFTWARE=1 \
    QT_X11_NO_MITSHM=1 \
    HOME=/tmp
WORKDIR /workspace
# Safe numeric default; host wrappers override it with the caller's UID/GID.
USER 65532:65532
CMD ["bash"]
