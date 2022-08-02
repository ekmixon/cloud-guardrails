# Copyright (c) 2021, salesforce.com, inc.
# All rights reserved.
# Licensed under the BSD 3-Clause license.
# For full license text, see the LICENSE file in the repo root
# or https://opensource.org/licenses/BSD-3-Clause
import logging
import json
import yaml
from cloud_guardrails.shared import utils
from cloud_guardrails.templates.config_template import get_config_template

logger = logging.getLogger(__name__)


class Config:
    def __init__(
        self,
        exclude_policies: dict,
        match_only_keywords: list = None,
        exclude_services: list = None,
        exclude_keywords: list = None,
    ):
        # This is not really needed by the object - just used for data validation
        self.supported_services = utils.get_service_names()
        self.exclude_policies = self._exclude_policies(exclude_policies)
        self.match_only_keywords = self._match_only_keywords(match_only_keywords)
        self.exclude_keywords = self._exclude_keywords(exclude_keywords)

        # Get the list of services excluded by the user
        self.exclude_services = self._exclude_services(exclude_services)

    def __str__(self):
        result = dict(
            match_only_keywords=self.match_only_keywords,
            exclude_services=self.exclude_services,
            exclude_policies=self.exclude_policies,
        )
        return json.dumps(result)

    def json(self):
        return dict(
            match_only_keywords=self.match_only_keywords,
            exclude_services=self.exclude_services,
            exclude_policies=self.exclude_policies,
        )

    @staticmethod
    def _match_only_keywords(keywords: list) -> list:
        return [x.lower() for x in keywords if x != ""] if keywords else []

    @staticmethod
    def _exclude_keywords(keywords: list) -> list:
        return [x.lower() for x in keywords if x != ""] if keywords else []

    def _exclude_policies(self, policies_dict: dict = None) -> dict:
        if not policies_dict:
            return {}
        result = {}
            # Let's just loop through and validate the service names.
        for service, values in policies_dict.items():
            if service not in self.supported_services:
                raise Exception(
                    f"Error: the provided service {service} is not in the list of supported services"
                )

                # Let's do some weird voodoo because the default template has empty strings as part of the dictionary
            service_values = [value for value in values if value != ""]
            result[service] = service_values
        return result

    def _exclude_services(self, services: list = None) -> list:
        exclude_services = []
        if services:
            for service in services:
                if service == "":
                    pass
                elif service in self.supported_services:
                    exclude_services.append(service)
                else:
                    raise Exception(
                        f"Error: the provided service {service} is not in the list of supported services"
                    )

        return exclude_services

    def is_keyword_match(self, policy_display_name: str) -> bool:
        result = False
        lowercase_name = policy_display_name.lower()
        if self.match_only_keywords:
            for keyword in self.match_only_keywords:
                if keyword in lowercase_name:
                    result = True
                    break
        return result

    def is_policy_excluded(self, service_name: str, display_name: str) -> bool:
        result = False
        # If the display name matches any of the keywords from exclude_keywords, then it's excluded
        if self.exclude_keywords:
            for keyword in self.exclude_keywords:
                if keyword.lower() in display_name.lower():
                    return True
        # If there is no list of excluded policies, it's not excluded
        if not self.exclude_policies:
            return result

        # If the service name is not in the list of excluded policies at all, then it's not excluded
        service_exists = self.exclude_policies.get(service_name, None)
        return (
            next(
                (
                    True
                    for service_name, service_policies in self.exclude_policies.items()
                    if display_name in service_policies
                ),
                result,
            )
            if service_exists
            else False
        )

    def is_excluded(self, service_name: str, display_name: str) -> bool:
        # Case: substrings from match_only_keywords are NOT in the display name
        if self.match_only_keywords and not self.is_keyword_match(
            policy_display_name=display_name
        ):
            return True

        # Case: Service is listed in excluded services
        if service_name in self.exclude_services:
            return True

        return bool(
            policy_excluded := self.is_policy_excluded(
                service_name=service_name, display_name=display_name
            )
        )

    def is_service_excluded(self, service_name: str) -> bool:
        return service_name in self.exclude_services


def get_default_config(exclude_services: list = None, match_only_keywords: list = None, exclude_keywords: list = None) -> Config:
    config_cfg = yaml.safe_load(DEFAULT_CONFIG_TEMPLATE)
    exclude_policies = config_cfg.get("exclude_policies", None)
    cfg_exclude_services = config_cfg.get("exclude_services", None)
    cfg_match_only_keywords = config_cfg.get("match_only_keywords", None)
    cfg_exclude_keywords = config_cfg.get("exclude_keywords", None)
    # Clean the empty strings
    if cfg_match_only_keywords:
        while "" in cfg_match_only_keywords:
            cfg_match_only_keywords.remove("")
    if cfg_exclude_services:
        while "" in cfg_exclude_services:
            cfg_exclude_services.remove("")
    if cfg_exclude_keywords:
        while "" in cfg_exclude_keywords:
            cfg_exclude_keywords.remove("")

    if exclude_services:
        cfg_exclude_services.extend(exclude_services)
    if match_only_keywords:
        cfg_match_only_keywords.extend(match_only_keywords)
    if exclude_keywords:
        cfg_exclude_keywords.extend(exclude_keywords)
    return Config(
        exclude_policies=exclude_policies,
        exclude_services=cfg_exclude_services,
        match_only_keywords=cfg_match_only_keywords,
        exclude_keywords=cfg_exclude_keywords,
    )


def get_config_from_file(config_file: str, exclude_services: list = None) -> Config:
    with open(config_file, "r") as yaml_file:
        config_cfg = yaml.safe_load(yaml_file)
    # Policies to exclude
    cfg_exclude_policies = config_cfg.get("exclude_policies", None)

    # Services to exclude
    # If exclude_services is supplied explicitly, combine that with whatever we find in the config file
    cfg_exclude_services = config_cfg.get("exclude_services", None)
    if exclude_services:
        cfg_exclude_services.extend(exclude_services)

    # Keywords to explicitly match
    match_only_keywords = config_cfg.get("match_only_keywords", None)

    # Keywords to explicitly avoid
    exclude_keywords = config_cfg.get("exclude_keywords", None)

    return Config(
        exclude_policies=cfg_exclude_policies,
        exclude_services=cfg_exclude_services,
        match_only_keywords=match_only_keywords,
        exclude_keywords=exclude_keywords,
    )


def get_empty_config() -> Config:
    return Config(
        exclude_policies={},
        exclude_services=None,
        match_only_keywords=None,
        exclude_keywords=None,
    )


DEFAULT_CONFIG_TEMPLATE = get_config_template()
DEFAULT_CONFIG = get_default_config()
