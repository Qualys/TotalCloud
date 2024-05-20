# TotalCloud CSPM Splunk Integration

This repository contains a Python script to fetch data from Qualys APIs for various cloud providers (AWS, Azure, GCP). The script sets up logging, handles API requests with retry logic, and fetches data for specified cloud providers.

## Prerequisites

- Python 3.6 or later
- Splunk instance
- Required Python libraries: `requests`, `PyYAML`

## Setup Guide

### 1. Clone the Repository

```sh
git clone https://github.com/yourusername/qualys-cloud-provider-fetcher.git
cd qualys-cloud-provider-fetcher
```

### 2. Install Python Dependencies

```sh
pip install -r requirements.txt
```

### 3. Set Qualys API Credentials and Platform URL
Edit the script qualys_fetcher.py to include your Qualys API credentials and platform URL:

```sh
# Set Qualys API Credentials and URL
USERNAME = "your_username"
PASSWORD = "your_password"
PLATFORM_URL = "https://qualysguard.qg1.apps.qualys.ca" # Refer https://www.qualys.com/platform-identification/
```

### Usage
You can utilize the power of scripted inputs to ingest CSPM information by following below mentioned steps.

**1. Build a script file**
* Create a script file under one of the splunk allowed directories. Verify whether your environment variable $SPLUNK_HOME is set. 
    * $SPLUNK_HOME/bin/scripts 
    * $SPLUNK_HOME/etc/apps/search/bin 
    * $SPLUNK_HOME/etc/apps/splunk_instrumentation/bin 
    * $SPLUNK_HOME/etc/system/bin 
* Copy the contents from the Qualys GitHub for the script file. 
* Ensure to replace username, password and platform url for TotalCloud in the script file. 
* Make the file executable and change the owner and group to user splunk. 
```sudo chmod +x cspmsplunk.py``` 

**2. Go to the Add New page**

**By Splunk Home**
* Click the Add Data link in Splunk Home. 
* Click Monitor to monitor a script on the local machine, or Forward to forward data from a script on a remote machine. Splunk Web displays the "Add Data - Select Source" page. 
* In the left pane, locate and select Scripts.

**By Splunk Settings**
* Click Settings in the upper right corner of Splunk Web. 
* Click Data Inputs. 
* Click Scripts. 
* Click New to add an input.

**3. Select the input source**
* In the Script Path drop down, select the path where the script resides. . Splunk Web updates the page to include a new drop-down list, "Script Name." 
* In the Script Name drop-down, select the script that you want to run. Splunk Web updates the page to populate the "Command" field with the script name. 
* In the Interval field, enter the amount of time (in seconds) that Splunk Enterprise should wait before invoking the script. You can schedule it to run daily or set up your own cron schedule. 
* Optionally, In the Source Name Override field, enter a new source name to override the default source value, if necessary. The default source name field is the path of your script file.  
* Click Next.


**4. Specify input settings**
* Select the source type for the script. You can choose Select to pick from the list of available source types on the local machine and select “json_no_timestamp”. 
* Select the "Searching and Reporting” as Application context for this input. 
* Set the Host name value. You have several choices for this setting. Example: TotalCloud 
* Set the Index that Splunk Enterprise should send data to. Leave the value as "default", unless you have defined multiple indexes to handle different types of events. In addition to indexes for user data. 
* Click Review.

**5. Review your choices**
* Review the settings. 
* If they do not match what you want, click < to go back to the previous step in the wizard. Otherwise, click Submit.

## Supported Cloud Types
AWS: Amazon Web Services
GCP: Google Cloud Platform
AZURE: Microsoft Azure

## Author
Yash Jhunjhunwala (Senior Solutions Architect, Cloud Security)
