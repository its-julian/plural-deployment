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
"""Command for compute reservations update."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from googlecloudsdk.api_lib.compute import base_classes
from googlecloudsdk.api_lib.compute import request_helper
from googlecloudsdk.api_lib.compute import utils
from googlecloudsdk.calliope import base
from googlecloudsdk.calliope import exceptions
from googlecloudsdk.command_lib.compute import flags as compute_flags
from googlecloudsdk.command_lib.compute.reservations import flags as r_flags
from googlecloudsdk.command_lib.compute.reservations import resource_args
from googlecloudsdk.command_lib.compute.reservations import util


def _ValidateArgs(args, support_share_with, support_share_with_flag):
  """Validates that both share settings arguments are mentioned.

  Args:
    args: The arguments given to the update command.
    support_share_with: Check the version.
    support_share_with_flag: Check if share_with is supported.
  """
  # Check the vesrion and share-with option.
  share_with = False
  parameter_names = ['--share-with', '--vm-count']
  one_option_exception_message = (
      'Please provide one of these options: 1- Specify share-with or '
      'add-share-with or remove-share-with to update the project list. 2- '
      'Specify reservation vm-count to resize. ')

  if support_share_with:
    has_share_with = False
    if support_share_with_flag:
      has_share_with = args.IsSpecified('share_with')
    has_add_share_with = args.IsSpecified('add_share_with')
    has_remove_share_with = args.IsSpecified('remove_share_with')
    if has_share_with or has_add_share_with or has_remove_share_with:
      share_with = True
    if (has_share_with and has_add_share_with) or (
        has_share_with and has_remove_share_with) or (has_add_share_with and
                                                      has_remove_share_with):
      raise exceptions.ConflictingArgumentsException('--share-with',
                                                     '--add-share-with',
                                                     '--remove-share-with')
    if has_remove_share_with:
      for project in getattr(args, 'remove_share_with', []):
        if not project.isnumeric():
          raise exceptions.InvalidArgumentException(
              '--remove-share-with',
              'Please specify project number (not project id/name).')

  # Check parameters (add_share_with and remove_share_with are on GA).
  if not share_with and not args.IsSpecified('vm_count'):
    raise exceptions.MinimumArgumentException(parameter_names,
                                              one_option_exception_message)


def _GetShareSettingUpdateRequest(
    args, reservation_ref, holder, support_share_with_flag):
  """Create Update Request for share-with.

  Returns:
  update request.
  Args:
   args: The arguments given to the update command.
   reservation_ref: reservation refrence.
   holder: base_classes.ComputeApiHolder.
   support_share_with_flag: Check if share_with is supported.
  """
  messages = holder.client.messages
  # Set updated properties and build update mask.
  share_settings = None
  setting_configs = 'projects'  # Only updating projects is supported now.
  if support_share_with_flag:
    if args.IsSpecified('share_with'):
      share_settings = util.MakeShareSettingsWithArgs(
          messages, args, setting_configs, share_with='share_with')
      update_mask = [
          'shareSettings.projectMap.' + project
          for project in getattr(args, 'share_with', [])
      ]
  if args.IsSpecified('add_share_with'):
    share_settings = util.MakeShareSettingsWithArgs(
        messages, args, setting_configs, share_with='add_share_with')
    update_mask = [
        'shareSettings.projectMap.' + project
        for project in getattr(args, 'add_share_with', [])
    ]
  elif args.IsSpecified('remove_share_with'):
    share_settings = messages.ShareSettings(
        shareType=messages.ShareSettings.ShareTypeValueValuesEnum
        .SPECIFIC_PROJECTS)
    update_mask = [
        'shareSettings.projectMap.' + project
        for project in getattr(args, 'remove_share_with', [])
    ]

  # Build reservation object using new share-settings.
  r_resource = util.MakeReservationMessage(messages, reservation_ref.Name(),
                                           share_settings, None, None,
                                           reservation_ref.zone)
  # Build update request.
  r_update_request = messages.ComputeReservationsUpdateRequest(
      reservation=reservation_ref.Name(),
      reservationResource=r_resource,
      paths=update_mask,
      project=reservation_ref.project,
      zone=reservation_ref.zone)

  return r_update_request


def _GetResizeRequest(args, reservation_ref, holder):
  """Create Update Request for vm_count.

  Returns:
  resize request.
  Args:
   args: The arguments given to the update command.
   reservation_ref: reservation refrence.
   holder: base_classes.ComputeApiHolder.
  """
  messages = holder.client.messages
  vm_count = None
  if args.IsSpecified('vm_count'):
    vm_count = args.vm_count

  # Build resize request.
  r_resize_request = messages.ComputeReservationsResizeRequest(
      reservation=reservation_ref.Name(),
      reservationsResizeRequest=messages.ReservationsResizeRequest(
          specificSkuCount=vm_count),
      project=reservation_ref.project,
      zone=reservation_ref.zone)

  return r_resize_request


@base.ReleaseTracks(base.ReleaseTrack.GA)
class Update(base.UpdateCommand):
  """Update Compute Engine reservations."""
  _support_share_with = True
  _support_share_with_flag = False

  @classmethod
  def Args(cls, parser):
    resource_args.GetReservationResourceArg().AddArgument(
        parser, operation_type='update')
    r_flags.GetAddShareWithFlag().AddToParser(parser)
    r_flags.GetRemoveShareWithFlag().AddToParser(parser)
    r_flags.GetVmCountFlag(False).AddToParser(parser)

  def Run(self, args):
    """Common routine for updating reservation."""
    holder = base_classes.ComputeApiHolder(self.ReleaseTrack())
    resources = holder.resources
    service = holder.client.apitools_client.reservations

    # Validate the command.
    _ValidateArgs(args, self._support_share_with, self._support_share_with_flag)
    reservation_ref = resource_args.GetReservationResourceArg(
    ).ResolveAsResource(
        args,
        resources,
        scope_lister=compute_flags.GetDefaultScopeLister(holder.client))

    result = list()
    errors = []
    share_with = False
    if self._support_share_with:
      if args.IsSpecified('add_share_with') or args.IsSpecified(
          'remove_share_with'):
        share_with = True
      if self._support_share_with_flag:
        if args.IsSpecified('share_with'):
          share_with = True

    if self._support_share_with and share_with:
      r_update_request = _GetShareSettingUpdateRequest(
          args, reservation_ref, holder, self._support_share_with_flag)
      # Invoke Reservation.update API.
      result.append(
          list(
              request_helper.MakeRequests(
                  requests=[(service, 'Update', r_update_request)],
                  http=holder.client.apitools_client.http,
                  batch_url=holder.client.batch_url,
                  errors=errors)))
      if errors:
        utils.RaiseToolException(errors)

    if args.IsSpecified('vm_count'):
      r_resize_request = _GetResizeRequest(args, reservation_ref, holder)
      # Invoke Reservation.resize API.
      result.append(
          holder.client.MakeRequests(([(service, 'Resize', r_resize_request)])))

    return result


@base.ReleaseTracks(base.ReleaseTrack.BETA, base.ReleaseTrack.ALPHA)
class UpdateBeta(Update):
  """Update Compute Engine reservations."""
  _support_share_with = True
  _support_share_with_flag = True

  @classmethod
  def Args(cls, parser):
    resource_args.GetReservationResourceArg().AddArgument(
        parser, operation_type='update')
    r_flags.GetShareWithFlag().AddToParser(parser)
    r_flags.GetAddShareWithFlag().AddToParser(parser)
    r_flags.GetRemoveShareWithFlag().AddToParser(parser)
    r_flags.GetVmCountFlag(False).AddToParser(parser)


Update.detailed_help = {
    'EXAMPLES':
        """
        To add `my-project` to the list of projects that are shared with a Compute Engine reservation, `my-reservation` in zone: `us-central1-a`, run:

            $ {command} my-reservation --add-share-with=my-project --zone=us-central1-a

        To remove `my-project` from the list of projects that are shared with a Compute Engine reservation, `my-reservation` in zone: `us-central1-a`, run:

            $ {command} my-reservation --remove-share-with=my-project --zone=us-central1-a

        To update the number of reserved VM instances to 500 for a Compute Engine reservation, `my-reservation` in zone: `us-central1-a`, run:

            $ {command} my-reservation --zone=us-central1-a --vm-count=500
        """
}

UpdateBeta.detailed_help = {
    'EXAMPLES':
        """
        To add `my-project` to the list of projects that are shared with a Compute Engine reservation, `my-reservation` in zone: `us-central1-a`, run:

            $ {command} my-reservation --add-share-with=my-project --zone=us-central1-a

        To remove `my-project` from the list of projects that are shared with a Compute Engine reservation, `my-reservation` in zone: `us-central1-a`, run:

            $ {command} my-reservation --remove-share-with=my-project --zone=us-central1-a

        To update the entire list of projects that are shared with a Compute Engine reservation, `my-reservation` in zone: `us-central1-a`, run:

            $ {command} my-reservation --share-with=my-project --zone=us-central1-a

        To update the number of reserved VM instances to 500 for a Compute Engine reservation, `my-reservation` in zone: `us-central1-a`, run:

            $ {command} my-reservation --zone=us-central1-a --vm-count=500
        """
}
