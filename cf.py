import boto3
import json
import os
import sys

def get_stack_status(stack_name):
    try:
        client = boto3.client('cloudformation')
        response = client.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        return stack['StackStatus'], stack.get('StackStatusReason', '')
    except Exception as e:
        return None, str(e)

def get_stack_events(stack_name):
    try:
        client = boto3.client('cloudformation')
        response = client.describe_stack_events(StackName=stack_name)
        return response['StackEvents']
    except Exception as e:
        return []

def find_rollback_trigger(events):
    for event in events:
        if event['ResourceStatus'] == 'CREATE_FAILED' or event['ResourceStatus'] == 'ROLLBACK_IN_PROGRESS':
            return event['LogicalResourceId'], event.get('ResourceStatusReason', 'No reason provided'), event['ResourceType']
    return None, None, None

def get_nested_stack_details(stack_name):
    nested_client = boto3.client('cloudformation')
    try:
        events = nested_client.describe_stack_events(StackName=stack_name)['StackEvents']
        for event in events:
            if event['ResourceStatus'] == 'CREATE_FAILED' or event['ResourceStatus'] == 'ROLLBACK_IN_PROGRESS':
                return event['LogicalResourceId'], event.get('ResourceStatusReason', 'No reason provided')
    except Exception as e:
        return None, f"Failed to get nested stack details: {str(e)}"
    return None, None

def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python cloudformation_status_checker.py <stack_name>"}))
        sys.exit(1)

    stack_name = sys.argv[1]

    # Step 1: Get the stack status
    stack_status, status_reason = get_stack_status(stack_name)

    if not stack_status:
        print(json.dumps({"error": "Failed to retrieve stack status", "reason": status_reason}))
        sys.exit(1)

    output = {"StackName": stack_name, "StackStatus": stack_status}

    # If rollback is detected, gather rollback details
    if 'ROLLBACK' in stack_status:
        events = get_stack_events(stack_name)
        resource_id, error_message, resource_type = find_rollback_trigger(events)

        if resource_id:
            output["RollbackTrigger"] = {
                "ResourceId": resource_id,
                "ErrorMessage": error_message,
                "ResourceType": resource_type,
            }

            # Check if the resource is a nested stack
            if resource_type == 'AWS::CloudFormation::Stack':
                nested_resource_id, nested_error_message = get_nested_stack_details(resource_id)
                if nested_resource_id:
                    output["NestedRollbackTrigger"] = {
                        "ResourceId": nested_resource_id,
                        "ErrorMessage": nested_error_message,
                    }
        else:
            output["RollbackTrigger"] = "No specific resource identified"

    # Output results in JSON format
    print(json.dumps(output, indent=4))

if __name__ == '__main__':
    main()
