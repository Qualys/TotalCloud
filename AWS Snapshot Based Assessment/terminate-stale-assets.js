const Sdk = require("aws-sdk");

const TagAppKey = "App";
const TagAppValue = "qualys-snapshot-scanner"

const nextMarkerLoop = async ({ apiCall, apiCallParams, postResponse }) => {
  let nextToken = undefined;
  let iteration = 0;

  while (nextToken != null || iteration == 0) {
    iteration += 1;
    const response = await apiCall({ ...apiCallParams, NextToken: nextToken });
    nextToken = response.NextToken;
    await postResponse(response);
  }
};

const terminateInstances = async ({ region }) => {
  const ec2 = new Sdk.EC2({
    region,
  });
  console.log("Terminating all instances for region", { region });
  let count = 0;

  await nextMarkerLoop({
    apiCall: (params) => ec2.describeInstances(params).promise(),
    apiCallParams: {
      MaxResults: 1000,
      Filters: [
        {
          Name: `tag:${TagAppKey}`,
          Values: [TagAppValue],
        },
      ],
    },
    /** @param {Sdk.DescribeInstancesResult} instances */
    postResponse: async (instances) => {
    const ids = [];

      for (const instance of instances.Reservations) {
        for (const ins of instance.Instances) {
          const state = ins.State?.Name;
          if (state !== "terminated") {
            ids.push(ins.InstanceId);
          }
        }
      }

      count += ids.length;

      if (ids.length > 0) {
        console.log(`Deleting instances: ${ids.length}`, { region });
        await ec2.terminateInstances({ InstanceIds: ids }).promise();
        console.log(`Deleted instances: ${ids.length}`, { region });
      }
    },
  });
  console.log(`Terminated instances completed, total deleted:${count}`, {
    region,
  });
};

const terminateSnapshots = async ({ region }) => {
  const ec2 = new Sdk.EC2({
    region,
  });
  console.log("Terminating all snapshots for region", { region });
  let count = 0;

  await nextMarkerLoop({
    apiCall: (params) => ec2.describeSnapshots(params).promise(),
    apiCallParams: {
      MaxResults: 50,
      Filters: [
        {
          Name: `tag:${TagAppKey}`,
          Values: [TagAppValue],
        },
      ],
      OwnerIds: ["self"],
    },
    postResponse: async (snapshots) => {
      console.log(`Deleting snapshots: ${snapshots.Snapshots.length}`, {
        region,
      });
      for (const ins of snapshots.Snapshots) {
        try {
          await ec2.deleteSnapshot({ SnapshotId: ins.SnapshotId }).promise();
        } catch(e) {
          console.error(e);
        }
        count += 1;
      }
      console.log(`Deleted snapshots: ${snapshots.Snapshots.length}`, {
        region,
      });
    },
  });
  console.log(`Terminated snapshots completed, total deleted:${count}`, {
    region,
  });
};

const terminateVolumes = async ({ region }) => {
  const ec2 = new Sdk.EC2({
    region,
  });
  console.log("Terminating all volumes for region", { region });
  let count = 0;

  await nextMarkerLoop({
    apiCall: (params) => ec2.describeVolumes(params).promise(),
    apiCallParams: {
      MaxResults: 50,
      Filters: [
        {
          Name: `tag:${TagAppKey}`,
          Values: [TagAppValue],
        },
      ],
    },
    postResponse: async (volumes) => {
      console.log(`Deleting volumes: ${volumes.Volumes.length}`, { region });
      for (const ins of volumes.Volumes) {
        try {
          await ec2.deleteVolume({ VolumeId: ins.VolumeId }).promise();
        } catch(e) {
          console.error(e);
        }
        count += 1;
      }
      console.log(`Deleted volumes: ${volumes.Volumes.length}`, { region });
    },
  });
  console.log(`Terminated volumes completed, total deleted:${count}`, {
    region,
  });
};

const main = async () => {
  const ec2 = new Sdk.EC2({});

  console.log("Fetching list of regions");

  const regions = await ec2.describeRegions({}).promise();

  for (const Region of regions.Regions) {
    const region = Region.RegionName;

    await terminateInstances({ region });
    await terminateSnapshots({ region });
    await terminateVolumes({ region });
  }
};

main().catch(console.error);
