import os
import json
import logging
from jinja2 import Environment, FileSystemLoader
from azure_guardrails.shared import utils
from azure_guardrails.shared.parameters_config import ParametersConfig
from azure_guardrails.shared.parameters_categorized import OverallCategorizedParameters

logger = logging.getLogger(__name__)


class TerraformTemplateWithParamsV5:
    """Terraform Template with Parameters"""
    def __init__(
            self,
            policy_id_pairs: dict,
            parameter_requirement_str: str,
            categorized_parameters: OverallCategorizedParameters,
            subscription_name: str = "",
            management_group: str = "",
            enforcement_mode: bool = False,
            category: str = "Testing",
    ):
        self.enforce = enforcement_mode
        self.name = self._initiative_name(
            subscription_name=subscription_name, management_group=management_group,
            parameter_requirement_str=parameter_requirement_str
        )
        self.subscription_name = subscription_name
        self.management_group = management_group
        self.category = category
        self.policy_id_pairs = self._policy_id_pairs(policy_id_pairs)
        self.categorized_parameters = categorized_parameters
        self.policy_definition_reference_parameters = self._policy_definition_reference_parameters()
        if enforcement_mode:
            self.enforcement_string = "true"
        else:
            self.enforcement_string = "false"

    def _initiative_name(self, subscription_name: str, management_group: str, parameter_requirement_str: str) -> str:
        if subscription_name == "" and management_group == "":
            raise Exception(
                "Please supply a value for the subscription name or the management group"
            )
        if self.enforce:
            parameter_requirement_str = f"{parameter_requirement_str}-Enforce"
        else:
            parameter_requirement_str = f"{parameter_requirement_str}-Audit"
        if subscription_name:
            initiative_name = utils.format_policy_name(subscription_name, parameter_requirement_str)
        else:
            initiative_name = utils.format_policy_name(management_group, parameter_requirement_str)
        return initiative_name

    @staticmethod
    def _policy_id_pairs(policy_id_pairs) -> dict:
        # Just validate the input, that's all
        all_valid_services = utils.get_service_names()
        for service_name, service_policies in policy_id_pairs.items():
            if service_name not in all_valid_services:
                raise Exception("The service provided is not a valid service")
            for policy_id, policy_details in service_policies.items():
                if not policy_details.get("display_name", None):
                    raise Exception("There should be a display name")
                if not policy_details.get("short_id", None):
                    raise Exception("There should be a short_id")
        return policy_id_pairs

    def _policy_definition_reference_parameters(self) -> dict:
        results = {}
        parameters = self.categorized_parameters.parameters()
        for service_name, service_policies in self.categorized_parameters.service_categorized_parameters.items():
            results[service_name] = {}
            # results["Kubernetes"] = {  "Do not allow privileged containers in Kubernetes cluster": { "excludedNamespaces": {stuff} }}
            for policy_definition_name, policy_definition_details in service_policies.items():
                results[service_name][policy_definition_name] = {}
                for parameter_name, parameter_value in policy_definition_details.items():
                    if parameter_name == "policy_id":
                        continue
                    # TODO: Determine if the user hasn't supplied certain parameters? You will have to determine the parameters they supplied vs the policies requested.
                    value = self.categorized_parameters.get_parameter_value_from_config(
                        display_name=policy_definition_name, parameter_name=parameter_name
                    )
                    if "\\" in value:
                        value = value.replace("\\", "\\\\")
                    if not value:
                        logger.critical("No value supplied by the user. Check it.")
                    parameter = dict(
                        parameter_name=parameter_name,
                        parameter_value=value,
                    )
                    results[service_name][policy_definition_name][parameter_name] = parameter
        return results

    @property
    def template_contents_json(self) -> dict:
        template_contents = dict(
            name=self.name,
            subscription_name=self.subscription_name,
            management_group=self.management_group,
            enforcement_mode=self.enforcement_string,
            policy_id_pairs=self.policy_id_pairs,
            policy_definition_reference_parameters=self.policy_definition_reference_parameters,
            category=self.category
        )
        return template_contents

    def rendered(self) -> str:
        template_path = os.path.join(os.path.dirname(__file__), "parameters-v5")
        env = Environment(loader=FileSystemLoader(template_path))  # nosec
        env.filters["debug"] = print
        env.filters['tojson'] = json.dumps
        env.filters['format_parameter_value'] = format_parameter_value
        template = env.get_template("policy-initiative-with-parameters-v5.tf")
        result = template.render(t=self.template_contents_json)
        return result


def format_parameter_value(value):
    """Formats policy_definition_reference.parameter_values.value properly"""
    result = ""

    def remove_escapes_and_single_quotes(some_val):
        some_val = some_val.replace("\\", "\\\\")
        some_val = some_val.replace("\'", '"')
        return some_val
    if isinstance(value, bool):
        # print(f"bool: {value}")
        # return value
        return str(value).lower()
    elif isinstance(value, int):
        # print(f"int: {value}")
        return value
    elif isinstance(value, list):
        return json.dumps(value)
    elif isinstance(value, dict):
        return json.dumps(value)
    elif isinstance(value, str):
        if "[" in value or "{" in value:
            result = remove_escapes_and_single_quotes(value)
            return json.dumps(result)
        else:
            return json.dumps(result)
    elif isinstance(value, type(None)):
        return json.dumps("")
    # elif "{" in value:
    #     result = value.replace("\\", "\\\\").replace("\'", '"')
    #     return result
    else:
        # print("We iterated through all types, nothing should be here.")
        # print(value)
        # result = remove_escapes_and_single_quotes(value)
        return json.dumps("")
# Instead of using replace('\\', '\\\\')|replace('\'', '"') in the Jinja2 template, since that doesn't handle strings well
