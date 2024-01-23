# Update Asset Tags in Bulk for AWS Account Connector

A Python script leveraging Qualys public APIs to efficiently update tags for existing detached AWS connectors in bulk.

## Prerequisites

- Python 3.x installed
- Required Python libraries installed. Install them using:
  ```bash
  pip install requests
  ```
- Qualys API credentials (username and password)
- CSV file containing connector data (e.g., connector_data.csv)

## Usage
1. Clone the repository:
```bash
git clone https://github.com/Qualys/TotalCloud.git
```
2. Navigate to the script directory:
```bash
cd Connectors/AWS/UpdateAssetTags
```
3. Configure the Qualys API endpoint in the script. Ref:- https://www.qualys.com/platform-identification/
- ex :- QUALYS_API_ENDPOINT="https://qualysapi.qg1.apps.qualys.ca"

4. Place your CSV file (connector_data.csv) in the same directory as the script.

5. Run the script:
```python
python aws_update_asset_tags.py
```

## Author
Yash Jhunjhunwala (Senior Solutions Architect, Cloud Security)
