### Scanning Lambda function with QScanner

### Prerequisites
https://docs.qualys.com/en/qscanner/latest/get_started/prerequisites.htm

### 📁 Folder Structure

```
project
├── scan-lambda-using-qscanner.sh
├── download_qscanner.sh # This will be downloaded using download_and_install_qscanner.sh
├── linux-(amd64|arm64)/ # This will be downloaded using download_and_install_qscanner.sh
│ └── qscanner # QScanner binary
├── app/
│ └── Dockerfile
│ └── app-lambda # repo will be copied here
```

### Once the folder structure is set, execute the script.
```commandline

chmod +x scan-lambda-using-qscanner.sh 

ACCESS_TOKEN=<ACCESS_TOKEN>  POD=<POD> IMAGE=<POD> $ABS_PATH_LAMBDA_DIR=<$ABS_PATH_LAMBDA_DIR> ./scan-lambda-using-qscanner.sh 

```
