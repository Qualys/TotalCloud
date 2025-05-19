### Scanning Lambda function with QScanner

### Prerequisites
https://docs.qualys.com/en/qscanner/latest/get_started/prerequisites.htm

### 📁 Folder Structure

```
project
├── scan-lambda-zip-using-qscanner.sh
├── download_qscanner.sh # This will be downloaded using download_and_install_qscanner.sh
├── linux-(amd64|arm64)/ # This will be downloaded using download_and_install_qscanner.sh
│ └── qscanner # QScanner binary
├── app/
│ └── Dockerfile
│ └── app-lambda # paste code repo in this directory
```
### Steps as per the folder structure provided

1. In the CICD pipeline after the build is complete, copy the `unzipped` files inside app/app-lambda dir where Dockerfile is present
2. execute scan-lambda-zip-using-qscanner.sh


### Once the folder structure is set, execute the script.
```commandline
chmod +x scan-lambda-zip-using-qscanner.sh 
ACCESS_TOKEN=<ACCESS_TOKEN>  POD=<POD> IMAGE=<POD> ./scan-lambda-zip-using-qscanner.sh 
```
