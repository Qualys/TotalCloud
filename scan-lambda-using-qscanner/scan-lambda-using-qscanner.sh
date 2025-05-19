#!/bin/bash

#============================================================
# Validate if one of the mentioned ARGS is empty
#============================================================
flag=true

if [ -z "$ACCESS_TOKEN" ]; then
    echo "The variable ACCESS_TOKEN is empty or not set."
    flag=false
fi

if [ -z "$POD" ]; then
    echo "The variable POD is empty or not set."
    flag=false
fi

if [ -z "$IMAGE" ]; then
    echo "The variable IMAGE is empty or not set."
    flag=false
fi

if ! $flag; then
    echo "Exiting Script - One or more env varibales not set properly."
    exit 1
fi

#============================================================
# download_and_install_qscanner
# # Refer https://www.qualys.com/downloads/qscanner/
#============================================================


#!/bin/bash

base_dir=$(pwd)  # Correctly capture the current working directory

echo ">>> Downloading QScanner"

curl -o download_qscanner.sh https://cask.qg1.apps.qualys.com/cs/p/-tfslPV9EXwxNCOi-IJE0JLZj0f_drFCtZnyhwirpPbXcoVtvicItJleq_6t7K5w/n/qualysincgov/b/us01-cask-artifacts/o/cs/qscanner/4.4.0-3/download_qscanner.sh

if [ -f "$base_dir/download_qscanner.sh" ]; then
    echo ">>> Successfully Downloaded QScanner"
else
    echo ">>> Failed to Download QScanner"
    exit 1
fi
chmod +x download_qscanner.sh


if [ -d linux-amd64 ]; then
    qscanner_binary_path="$(pwd)/linux-amd64"
elif [ -d linux-arm64 ]; then
    qscanner_binary_path="$(pwd)/linux-arm64"
else
    qscanner_binary_path=""
fi

if [ -d "$qscanner_binary_path" ]; then
    echo ">>> QScanner Binary is already downloaded at '$qscanner_binary_path'"
else
    echo ">>> QScanner Binary does not exist."
    echo ">>> Downloading QScanner Binary - Started"
    pwd
    bash download_qscanner.sh
    echo ">>> Downloaded QScanner Binary - Finished"

    # Try setting qscanner_binary_path again in case it got created during download
    if [ -d linux-amd64 ]; then
        qscanner_binary_path="$(pwd)/linux-amd64"
    elif [ -d linux-arm64 ]; then
        qscanner_binary_path="$(pwd)/linux-arm64"
    fi
fi

echo ">>> QScanner Binary downloaded at '$qscanner_binary_path'"

cd $qscanner_binary_path
./qscanner --version


if ./qscanner --version | grep -q "qscanner version"; then
    echo ">>> QScanner is installed"
else
    echo ">>> QScanner not found in output. Check Installation"
    exit 1
fi

#============================================================
# Build Image
#============================================================

cd $base_dir/app
pwd
ls
docker build -t $IMAGE .

#============================================================
# Final Step - Scannnig for vulnerabilities using Qscanner
#============================================================

cd $qscanner_binary_path
pwd
ls
echo ">>> Current Working Directory: $(qscanner_binary_path)"

echo ">>> Scanning for vulnerabilities using Qscanner, image $IMAGE\n"
./qscanner image $IMAGE --pod $POD --access-token $ACCESS_TOKEN
