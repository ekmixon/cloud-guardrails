variable "name" { default = "{{ t.name }}" }
variable "subscription_name" { default = "{{ t.subscription_name }}" }
variable "management_group" { default = "{{ t.management_group }}" }
variable "enforcement_mode" { default = {{ t.enforcement_mode }} }

variable "category" {
  type    = string
  default = "Testing"
}
provider "azurerm" {
  features {}
}

locals {
  policy_names = [{% for service_name, policies_with_params in t.policies_sorted_by_service.items() %}
    # -----------------------------------------------------------------------------------------------------------------
    # {{ service_name }}
    # -----------------------------------------------------------------------------------------------------------------{% for key in policies_with_params %}
    "{{ key }}",{% endfor %}{% endfor %}
  ]
  policy_definition_map = zipmap(
    data.azurerm_policy_definition.{{ t.name }}_definition_lookups.*.display_name,
    data.azurerm_policy_definition.{{ t.name }}_definition_lookups.*.id
  )
}

# ---------------------------------------------------------------------------------------------------------------------
# Conditional data lookups: If the user supplies management group, look up the ID of the management group
# ---------------------------------------------------------------------------------------------------------------------
data "azurerm_management_group" "{{ t.name }}" {
  count = var.management_group != "" ? 1 : 0
  name  = var.management_group
}

### If the user supplies subscription, look up the ID of the subscription
data "azurerm_subscriptions" "{{ t.name }}" {
  count                 = var.subscription_name != "" ? 1 : 0
  display_name_contains = var.subscription_name
}

locals {
  scope = var.management_group != "" ? data.azurerm_management_group.{{ t.name }}[0].id : element(data.azurerm_subscriptions.{{ t.name }}[0].subscriptions.*.id, 0)
}

# ---------------------------------------------------------------------------------------------------------------------
# Azure Policy Definition Lookups
# ---------------------------------------------------------------------------------------------------------------------

data "azurerm_policy_definition" "{{ t.name }}_definition_lookups" {
  count        = length(local.policy_names)
  display_name = local.policy_names[count.index]
}

# ---------------------------------------------------------------------------------------------------------------------
# Azure Policy Initiative Definition
# ---------------------------------------------------------------------------------------------------------------------

resource "azurerm_policy_set_definition" "{{ t.name }}_guardrails" {
  name                  = var.name
  policy_type           = "Custom"
  display_name          = var.name
  description           = var.name
  management_group_name = var.management_group == "" ? null : var.management_group
  metadata = tostring(jsonencode({
    category = var.category
  }))

  {% for service_name, service_policy_details in t.policy_definition_reference_parameters.items() %}
  {% for policy_definition_name, policy_definition_params in service_policy_details.items() %}
  policy_definition_reference {
    policy_definition_id = lookup(local.policy_definition_map, "{{ policy_definition_name }}")
    parameter_values = jsonencode({ {% for key, value in policy_definition_params.items() %}
      {{ value.name }} = { "value" : "{{ value.policy_definition_reference_value }}" }{% endfor %}
    })
    reference_id = null
  }
  {% endfor %}{% endfor %}

  parameters = <<PARAMETERS
{{ t.initiative_parameters }}
PARAMETERS
}

# ---------------------------------------------------------------------------------------------------------------------
# Azure Policy Assignments
# Apply the Policy Initiative to the specified scope
# ---------------------------------------------------------------------------------------------------------------------
resource "azurerm_policy_assignment" "{{ t.name }}_guardrails" {
  name                 = var.name
  policy_definition_id = azurerm_policy_set_definition.{{ t.name }}_guardrails.id
  scope                = local.scope
  enforcement_mode     = var.enforcement_mode
  parameters = jsonencode({
    {{ t.policy_assignment_parameters }}
})
}


# ---------------------------------------------------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------------------------------------------------
output "policy_assignment_ids" {
  value       = azurerm_policy_assignment.{{ t.name }}_guardrails.*.id
  description = "The IDs of the Policy Assignments."
}

output "scope" {
  value       = local.scope
  description = "The target scope - either the management group or subscription, depending on which parameters were supplied"
}

output "policy_set_definition_id" {
  value       = azurerm_policy_set_definition.{{ t.name }}_guardrails.id
  description = "The ID of the Policy Set Definition."
}