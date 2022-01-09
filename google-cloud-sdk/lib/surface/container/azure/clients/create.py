# -*- coding: utf-8 -*- #
# Copyright 2021 Google LLC. All Rights Reserved.
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
"""Command to create an Azure client."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from googlecloudsdk.api_lib.container.azure import util as azure_api_util
from googlecloudsdk.calliope import base
from googlecloudsdk.command_lib.container.azure import resource_args
from googlecloudsdk.command_lib.container.azure import util as command_util
from googlecloudsdk.command_lib.container.gkemulticloud import constants
from googlecloudsdk.command_lib.container.gkemulticloud import endpoint_util
from googlecloudsdk.command_lib.container.gkemulticloud import flags
from googlecloudsdk.core import log


# Command needs to be in one line for the docgen tool to format properly.
_EXAMPLES = """
To create an Azure client named ``my-client'' in
location ``us-west1'', run:

$ {command} my-client --location=us-west1 --application-id=APP_ID --tenant-id=TENANT_ID
"""


@base.ReleaseTracks(base.ReleaseTrack.ALPHA, base.ReleaseTrack.GA)
class Create(base.CreateCommand):
  """Create an Azure client."""

  detailed_help = {"EXAMPLES": _EXAMPLES}

  @staticmethod
  def Args(parser):
    resource_args.AddAzureClientResourceArg(parser, "to create")
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Azure Active Directory (AAD) tenant ID (GUID) to associate with the client."
    )
    parser.add_argument(
        "--application-id",
        required=True,
        dest="app_id",
        help="Azure Active Directory (AAD) Application/Client ID (GUID).")
    flags.AddValidateOnly(parser, "creation of the client")
    parser.display_info.AddFormat(command_util.CLIENT_FORMAT)

  def Run(self, args):
    """Runs the create command."""
    tenant_id = args.tenant_id
    app_id = args.app_id
    validate_only = args.validate_only

    track = base.ReleaseTrack.ALPHA
    with endpoint_util.GkemulticloudEndpointOverride(
        resource_args.ParseAzureClientResourceArg(args).locationsId, track):
      client_ref = resource_args.ParseAzureClientResourceArg(args)
      api_client = azure_api_util.ClientsClient(track=track)
      api_client.Create(
          client_ref=client_ref,
          tenant_id=tenant_id,
          application_id=app_id,
          validate_only=validate_only)

      log.CreatedResource(client_ref, kind=constants.AZURE_CLIENT_KIND)
