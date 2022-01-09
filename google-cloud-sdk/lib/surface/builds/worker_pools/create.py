# -*- coding: utf-8 -*- #
# Copyright 2018 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Create worker pool command."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from googlecloudsdk.api_lib.cloudbuild import cloudbuild_exceptions
from googlecloudsdk.api_lib.cloudbuild import cloudbuild_util
from googlecloudsdk.api_lib.cloudbuild import workerpool_config
from googlecloudsdk.api_lib.compute import utils as compute_utils
from googlecloudsdk.api_lib.util import waiter
from googlecloudsdk.calliope import base
from googlecloudsdk.command_lib.cloudbuild import workerpool_flags
from googlecloudsdk.command_lib.util.apis import arg_utils
from googlecloudsdk.core import log
from googlecloudsdk.core import properties
from googlecloudsdk.core import resources


@base.ReleaseTracks(base.ReleaseTrack.GA)
class Create(base.CreateCommand):
  """Create a worker pool for use by Google Cloud Build."""

  detailed_help = {
      'DESCRIPTION':
          '{description}',
      'EXAMPLES':
          """\
          To create a worker pool named `wp1` in region `us-central1`, run:

            $ {command} wp1 --region=us-central1

          To create a worker pool in project `p1` in region `us-central1` where workers are of machine type
          `e2-standard-2` and are peered to the VPC network `projects/123/global/networks/default` and have a disk size of
          64GB, run:

            $ {command} wp1 --project=p1 --region=us-central1 \
                --peered-network=projects/123/global/networks/default \
                --worker-machine-type=e2-standard-2 \
                --worker-disk-size=64GB
          """,
  }

  @staticmethod
  def Args(parser):
    """Register flags for this command.

    Args:
      parser: An argparse.ArgumentParser-like object. It is mocked out in order
        to capture some information, but behaves like an ArgumentParser.
    """
    parser = workerpool_flags.AddWorkerpoolCreateArgs(parser,
                                                      base.ReleaseTrack.GA)
    parser.display_info.AddFormat("""
          table(
            name.segment(-1),
            createTime.date('%Y-%m-%dT%H:%M:%S%Oz', undefined='-'),
            state
          )
        """)

  def Run(self, args):
    """This is what gets called when the user runs this command.

    Args:
      args: an argparse namespace. All the arguments that were provided to this
        command invocation.

    Returns:
      Some value that we want to have printed later.
    """

    wp_name = args.WORKER_POOL
    wp_region = args.region

    release_track = self.ReleaseTrack()
    client = cloudbuild_util.GetClientInstance(release_track)
    messages = cloudbuild_util.GetMessagesModule(release_track)

    # Get the workerpool proto from either the flags or the specified file.
    wp = messages.WorkerPool()
    if args.config_from_file is not None:
      try:
        wp = workerpool_config.LoadWorkerpoolConfigFromPath(
            args.config_from_file, messages)
        # Don't allow a worker pool config for hybrid worker pools in any other
        # track but alpha.
        if release_track != base.ReleaseTrack.ALPHA:
          if wp.hybridPoolConfig is not None:
            raise cloudbuild_exceptions.HybridNonAlphaConfigError
      except cloudbuild_exceptions.ParseProtoException as err:
        log.err.Print(
            '\nFailed to parse configuration from file. If you'
            ' were a Private Preview user, note that the format for this'
            ' file has changed slightly for GA.\n')
        raise err
    else:
      wp.privatePoolV1Config = messages.PrivatePoolV1Config()

      network_config = messages.NetworkConfig()
      if args.peered_network is not None:
        network_config.peeredNetwork = args.peered_network
      # All of the egress flags are mutually exclusive with each other.
      if args.no_public_egress or (release_track == base.ReleaseTrack.GA and
                                   args.no_external_ip):
        network_config.egressOption = messages.NetworkConfig.EgressOptionValueValuesEnum.NO_PUBLIC_EGRESS
      wp.privatePoolV1Config.networkConfig = network_config

      worker_config = messages.WorkerConfig()
      if args.worker_machine_type is not None:
        worker_config.machineType = args.worker_machine_type
      if args.worker_disk_size is not None:
        worker_config.diskSizeGb = compute_utils.BytesToGb(
            args.worker_disk_size)
      wp.privatePoolV1Config.workerConfig = worker_config

    parent = properties.VALUES.core.project.Get(required=True)

    # Get the parent project.location ref
    parent_resource = resources.REGISTRY.Create(
        collection='cloudbuild.projects.locations',
        projectsId=parent,
        locationsId=wp_region)

    # Send the Create request
    created_op = client.projects_locations_workerPools.Create(
        messages.CloudbuildProjectsLocationsWorkerPoolsCreateRequest(
            workerPool=wp,
            parent=parent_resource.RelativeName(),
            workerPoolId=wp_name))

    op_resource = resources.REGISTRY.ParseRelativeName(
        created_op.name, collection='cloudbuild.projects.locations.operations')
    created_wp = waiter.WaitFor(
        waiter.CloudOperationPoller(client.projects_locations_workerPools,
                                    client.projects_locations_operations),
        op_resource, 'Creating worker pool')

    # Get the workerpool ref
    wp_resource = resources.REGISTRY.Parse(
        None,
        collection='cloudbuild.projects.locations.workerPools',
        api_version=cloudbuild_util.RELEASE_TRACK_TO_API_VERSION[release_track],
        params={
            'projectsId': parent,
            'locationsId': wp_region,
            'workerPoolsId': created_wp.name,
        })

    log.CreatedResource(wp_resource)

    return created_wp


@base.ReleaseTracks(base.ReleaseTrack.BETA)
class CreateBeta(Create):
  """Create a worker pool for use by Google Cloud Build."""

  @staticmethod
  def Args(parser):
    """Register flags for this command.

    Args:
      parser: An argparse.ArgumentParser-like object. It is mocked out in order
        to capture some information, but behaves like an ArgumentParser.
    """
    parser = workerpool_flags.AddWorkerpoolCreateArgs(parser,
                                                      base.ReleaseTrack.BETA)
    parser.display_info.AddFormat("""
          table(
            name,
            createTime.date('%Y-%m-%dT%H:%M:%S%Oz', undefined='-'),
            state
          )
        """)


@base.ReleaseTracks(base.ReleaseTrack.ALPHA)
class CreateAlpha(Create):
  """Create a worker pool for use by Google Cloud Build."""

  @staticmethod
  def Args(parser):
    """Register flags for this command.

    Args:
      parser: An argparse.ArgumentParser-like object. It is mocked out in order
        to capture some information, but behaves like an ArgumentParser.
    """
    parser = workerpool_flags.AddWorkerpoolCreateArgs(parser,
                                                      base.ReleaseTrack.ALPHA)
    parser.display_info.AddFormat("""
          table(
            name.segment(-1),
            createTime.date('%Y-%m-%dT%H:%M:%S%Oz', undefined='-'),
            state
          )
        """)

  def Run(self, args):
    """This is what gets called when the user runs this command.

    Args:
      args: an argparse namespace. All the arguments that were provided to this
        command invocation.

    Returns:
      Some value that we want to have printed later.
    """

    wp_name = args.WORKER_POOL
    wp_region = args.region

    release_track = self.ReleaseTrack()
    client = cloudbuild_util.GetClientInstance(release_track)
    messages = cloudbuild_util.GetMessagesModule(release_track)

    # Get the workerpool proto from either the flags or the specified file.
    wp = messages.WorkerPool()
    if args.config_from_file is not None:
      try:
        wp = workerpool_config.LoadWorkerpoolConfigFromPath(
            args.config_from_file, messages)
        if wp.hybridPoolConfig is not None:
          if wp_region not in cloudbuild_util.CBH_SUPPORTED_REGIONS:
            raise cloudbuild_exceptions.HybridUnsupportedRegionError(wp_region)
      except cloudbuild_exceptions.ParseProtoException as err:
        log.err.Print('\nFailed to parse configuration from file.\n')
        raise err
    else:
      if args.membership is not None:
        if wp_region not in cloudbuild_util.CBH_SUPPORTED_REGIONS:
          raise cloudbuild_exceptions.HybridUnsupportedRegionError(wp_region)

        wp.hybridPoolConfig = messages.HybridPoolConfig()
        wp.hybridPoolConfig.membership = args.membership

        worker_config = messages.HybridWorkerConfig()
        if args.default_build_disk_size is not None:
          worker_config.diskSizeGb = compute_utils.BytesToGb(
              args.default_build_disk_size)
        if args.default_build_memory is not None:
          worker_config.memoryGb = cloudbuild_util.BytesToGb(
              args.default_build_memory)
        if args.default_build_vcpu_count is not None:
          worker_config.vcpuCount = args.default_build_vcpu_count
        wp.hybridPoolConfig.defaultWorkerConfig = worker_config

        wp.hybridPoolConfig.builderImageCaching = arg_utils.ChoiceToEnum(
            args.builder_image_caching,
            messages.HybridPoolConfig.BuilderImageCachingValueValuesEnum)
        if args.caching_storage_class is not None:
          wp.hybridPoolConfig.cachingStorageClass = args.caching_storage_class
      else:
        wp.privatePoolV1Config = messages.PrivatePoolV1Config()

        network_config = messages.NetworkConfig()
        if args.peered_network is not None:
          network_config.peeredNetwork = args.peered_network
        # All of the egress flags are mutually exclusive with each other.
        if args.no_public_egress or (release_track == base.ReleaseTrack.GA and
                                     args.no_external_ip):
          network_config.egressOption = messages.NetworkConfig.EgressOptionValueValuesEnum.NO_PUBLIC_EGRESS
        wp.privatePoolV1Config.networkConfig = network_config

        worker_config = messages.WorkerConfig()
        if args.worker_machine_type is not None:
          worker_config.machineType = args.worker_machine_type
        if args.worker_disk_size is not None:
          worker_config.diskSizeGb = compute_utils.BytesToGb(
              args.worker_disk_size)
        wp.privatePoolV1Config.workerConfig = worker_config

    parent = properties.VALUES.core.project.Get(required=True)

    # Get the parent project.location ref
    parent_resource = resources.REGISTRY.Create(
        collection='cloudbuild.projects.locations',
        projectsId=parent,
        locationsId=wp_region)

    # Send the Create request
    created_op = client.projects_locations_workerPools.Create(
        messages.CloudbuildProjectsLocationsWorkerPoolsCreateRequest(
            workerPool=wp,
            parent=parent_resource.RelativeName(),
            workerPoolId=wp_name))

    op_resource = resources.REGISTRY.ParseRelativeName(
        created_op.name, collection='cloudbuild.projects.locations.operations')
    created_wp = waiter.WaitFor(
        waiter.CloudOperationPoller(client.projects_locations_workerPools,
                                    client.projects_locations_operations),
        op_resource, 'Creating worker pool')

    # Get the workerpool ref
    wp_resource = resources.REGISTRY.Parse(
        None,
        collection='cloudbuild.projects.locations.workerPools',
        api_version=cloudbuild_util.RELEASE_TRACK_TO_API_VERSION[release_track],
        params={
            'projectsId': parent,
            'locationsId': wp_region,
            'workerPoolsId': created_wp.name,
        })

    log.CreatedResource(wp_resource)

    return created_wp
