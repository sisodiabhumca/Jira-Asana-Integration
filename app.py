from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
from jira import JIRA
import asana
import json
from datetime import datetime
import uuid

app = Flask(__name__, static_url_path='/static')
CORS(app)
load_dotenv()

# Initialize API clients
jira_url = os.getenv('JIRA_URL')
if jira_url.endswith('/'):  # Remove trailing slash if present
    jira_url = jira_url.rstrip('/')

# API configurations
JIRA_API_URL = os.getenv('JIRA_URL', '').rstrip('/')
JIRA_AUTH = (os.getenv('JIRA_EMAIL'), os.getenv('JIRA_API_TOKEN'))
ASANA_API_URL = 'https://app.asana.com/api/1.0'
ASANA_TOKEN = os.getenv('ASANA_ACCESS_TOKEN')

# Store selected workspaces
selected_workspaces = {
    'jira': None,
    'asana': None
}

# Store field mappings
field_mappings_store = {
    'jira_to_asana': {},
    'asana_to_jira': {}
}

# Store available fields
available_fields = {
    'jira': {},
    'asana': {}
}

# Helper functions

def make_jira_request(endpoint, method='GET', data=None):
    """Make a request to Jira REST API"""
    url = urljoin(JIRA_API_URL, endpoint)
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.request(
            method,
            url,
            auth=JIRA_AUTH,
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        app.logger.error(f'Jira API error: {str(e)}')
        raise

def make_asana_request(endpoint, method='GET', data=None):
    """Make a request to Asana REST API"""
    url = urljoin(ASANA_API_URL, endpoint)
    headers = {
        'Authorization': f'Bearer {ASANA_TOKEN}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        app.logger.error(f'Asana API error: {str(e)}')
        raise

@app.route('/get_jira_workspaces', methods=['GET'])
def get_jira_workspaces():
    """Get all Jira projects"""
    try:
        response = make_jira_request('rest/api/2/project')
        projects = response.get('values', [])
        
        if not projects:
            return jsonify({'error': 'No Jira projects found'}), 404
            
        workspaces = []
        for project in projects:
            workspaces.append({
                'id': project['key'],
                'name': f"{project['name']} ({project['key']})",
                'key': project['key'],
                'type': 'project'
            })
        return jsonify(workspaces)
    except Exception as e:
        app.logger.error(f'Error getting Jira workspaces: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/get_asana_workspaces', methods=['GET'])
def get_asana_workspaces():
    """Get all Asana workspaces"""
    try:
        response = make_asana_request('workspaces')
        workspaces = response.get('data', [])
        workspaces = []
        for workspace in asana_client.workspaces.find_all():
            try:
                workspaces.append({
                    'id': workspace['gid'],
                    'name': workspace['name'],
                    'gid': workspace['gid']
                })
            except Exception as e:
                app.logger.error(f'Error processing Asana workspace {workspace.get("gid")}: {str(e)}')
                continue
        
        if not workspaces:
            return jsonify({'error': 'No Asana workspaces found'}), 404
            
        # Sort by workspace name
        workspaces.sort(key=lambda x: x['name'])
        
        return jsonify(workspaces)
    except Exception as e:
        app.logger.error(f'Error getting Asana workspaces: {str(e)}')
        return jsonify({'error': f'Failed to connect to Asana: {str(e)}'}), 500

@app.route('/select_workspace', methods=['POST'])
def select_workspace():
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        platform = data.get('platform')
        workspace_id = data.get('workspace_id')
        
        if not platform or not workspace_id:
            return jsonify({'error': 'Missing required parameters'}), 400
            
        if platform not in ['jira', 'asana']:
            return jsonify({'error': 'Invalid platform'}), 400
            
        # Validate workspace exists
        if platform == 'jira':
            try:
                project = jira_client.project(workspace_id)
                if not project:
                    return jsonify({'error': 'Jira project not found'}), 404
            except Exception as e:
                return jsonify({'error': f'Invalid Jira project: {str(e)}'}), 404
                
        else:  # asana
            try:
                workspace = asana_client.workspaces.find_by_id(workspace_id)
                if not workspace:
                    return jsonify({'error': 'Asana workspace not found'}), 404
            except Exception as e:
                return jsonify({'error': f'Invalid Asana workspace: {str(e)}'}), 404
                
        # Store the selection
        selected_workspaces[platform] = workspace_id
        return jsonify({
            'status': 'success',
            'workspace_id': workspace_id,
            'platform': platform
        })
    except Exception as e:
        app.logger.error(f'Error selecting workspace: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_fields', methods=['GET'])
def get_fields():
    try:
        # Get Jira fields
        jira_fields = jira_client.fields()
        jira_field_options = [{
            'id': field['id'],
            'name': field['name']
        } for field in jira_fields]

        # Get Asana fields
        asana_fields = []
        for project in asana_client.projects.find_all():
            custom_fields = asana_client.custom_fields.find_by_project(project['gid'])
            for field in custom_fields:
                asana_fields.append({
                    'id': field['gid'],
                    'name': field['name']
                })

        return jsonify({
            'jira_fields': jira_field_options,
            'asana_fields': asana_fields
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save_mappings', methods=['POST'])
def save_mappings():
    try:
        data = request.json
        field_mappings.update(data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_sync', methods=['POST'])
def test_sync():
    try:
        data = request.json
        direction = data.get('direction', 'jira_to_asana')
        
        if not selected_workspaces['jira'] or not selected_workspaces['asana']:
            return jsonify({'error': 'Please select both workspaces first'}), 400
            
        if direction == 'jira_to_asana':
            # Test Jira connection
            test_issue = jira_client.issue('TEST-1')  # Try to get a test issue
            if not test_issue:
                return jsonify({'error': 'Could not connect to Jira'}), 500
                
            # Test Asana connection
            test_task = asana_client.tasks.find_by_id('12345')  # Try to get a test task
            if not test_task:
                return jsonify({'error': 'Could not connect to Asana'}), 500
                
            return jsonify({
                'status': 'success',
                'message': 'Test sync successful! Connection verified.'
            })
            
        else:  # asana_to_jira
            # Test Asana connection
            test_task = asana_client.tasks.find_by_id('12345')  # Try to get a test task
            if not test_task:
                return jsonify({'error': 'Could not connect to Asana'}), 500
                
            # Test Jira connection
            test_issue = jira_client.issue('TEST-1')  # Try to get a test issue
            if not test_issue:
                return jsonify({'error': 'Could not connect to Jira'}), 500
                
            return jsonify({
                'status': 'success',
                'message': 'Test sync successful! Connection verified.'
            })
    except Exception as e:
        app.logger.error(f'Test sync failed: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/sync', methods=['POST'])
def sync():
    try:
        data = request.json
        direction = data.get('direction', 'jira_to_asana')

        if direction == 'jira_to_asana':
            return sync_jira_to_asana()
        else:
            return sync_asana_to_jira()
    except Exception as e:
        app.logger.error(f'Sync failed: {str(e)}')
        return jsonify({'error': str(e)}), 500

# Test data for Jira
TEST_JIRA_ISSUES = [
    {
        'summary': 'Test Task 1',
        'description': 'This is a test task from Jira',
        'priority': 'High',
        'status': 'To Do'
    },
    {
        'summary': 'Test Task 2',
        'description': 'Another test task from Asana',
        'priority': 'Medium',
        'status': 'In Progress'
    }
]

# Test data for Asana
TEST_ASANA_TASKS = [
    {
        'name': 'Test Task 1',
        'notes': 'This is a test task from Asana',
        'priority': 1,
        'status': 'not_started'
    },
    {
        'name': 'Test Task 2',
        'notes': 'Another test task from Asana',
        'priority': 2,
        'status': 'in_progress'
    }
]

@app.route('/sync_jira_to_asana', methods=['GET'])
def sync_jira_to_asana():
    try:
        if not selected_workspaces['jira'] or not selected_workspaces['asana']:
            return jsonify({'error': 'Please select both Jira and Asana workspaces first'}), 400

        # Get issues from selected Jira workspace
        jql_query = f'project = {selected_workspaces["jira"]}'
        issues = jira_client.search_issues(jql_query)
        
        # Get Asana workspace
        asana_workspace = asana_client.workspaces.find_by_id(selected_workspaces['asana'])
        
        # Create project in selected Asana workspace
        test_project = asana_client.projects.create_project({
            'name': f'Jira Sync - {selected_workspaces["jira"]}',
            'workspace': asana_workspace['gid']
        })

        # Create tasks in Asana
        for issue in issues:
            task_data = {
                'name': issue.fields.summary,
                'notes': issue.fields.description,
                'projects': [test_project['gid']],
                'priority': issue.fields.priority.name if hasattr(issue.fields, 'priority') else 'Normal',
                'custom_fields': {
                    'status': issue.fields.status.name if hasattr(issue.fields, 'status') else 'To Do'
                }
            }
            asana_client.tasks.create_task(task_data)

        return jsonify({
            'status': 'success',
            'message': 'Tasks synced successfully',
            'project_id': test_project['gid']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/sync_asana_to_jira', methods=['GET'])
def sync_asana_to_jira():
    try:
        if not selected_workspaces['jira'] or not selected_workspaces['asana']:
            return jsonify({'error': 'Please select both Jira and Asana workspaces first'}), 400

        # Get tasks from selected Asana workspace
        tasks = []
        for project in asana_client.projects.find_by_workspace(selected_workspaces['asana']):
            project_tasks = asana_client.tasks.find_by_project(project['gid'])
            tasks.extend(project_tasks)

        # Create issues in selected Jira workspace
        for task in tasks:
            issue_data = {
                'fields': {
                    'project': {'key': selected_workspaces['jira']},
                    'summary': task['name'],
                    'description': task['notes'],
                    'issuetype': {'name': 'Task'},
                    'priority': {'name': 'Medium'},
                    'customfield_10000': task['priority'] if 'priority' in task else 2,  # Custom field for priority
                    'customfield_10001': task['status'] if 'status' in task else 'To Do'  # Custom field for status
                }
            }
            jira_client.create_issue(fields=issue_data)

        return jsonify({
            'status': 'success',
            'message': 'Issues synced successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_asana_fields', methods=['GET'])
def get_asana_fields():
    try:
        # Get custom fields for the selected workspace
        workspace_id = selected_workspaces.get('asana')
        if not workspace_id:
            return jsonify({'error': 'No Asana workspace selected'}), 400
            
        # Get all custom fields from the workspace
        custom_fields = list(asana_client.custom_fields.find_by_workspace(workspace_id))
        
        # Get all default fields with their types
        default_fields = {
            'name': {'name': 'Name', 'type': 'text'},
            'notes': {'name': 'Notes', 'type': 'text'},
            'status': {'name': 'Status', 'type': 'enum'},
            'priority': {'name': 'Priority', 'type': 'enum'},
            'assignee': {'name': 'Assignee', 'type': 'user'},
            'created_at': {'name': 'Created Date', 'type': 'date'},
            'modified_at': {'name': 'Modified Date', 'type': 'date'},
            'due_date': {'name': 'Due Date', 'type': 'date'},
            'due_at': {'name': 'Due Time', 'type': 'time'},
            'completed': {'name': 'Completed', 'type': 'boolean'},
            'custom_fields': {'name': 'Custom Fields', 'type': 'custom'},
            'tags': {'name': 'Tags', 'type': 'list'},
            'followers': {'name': 'Followers', 'type': 'user_list'},
            'workspace': {'name': 'Workspace', 'type': 'workspace'},
            'team': {'name': 'Team', 'type': 'team'},
            'parent': {'name': 'Parent Task', 'type': 'task'},
            'memberships': {'name': 'Projects', 'type': 'project_list'},
            'dependencies': {'name': 'Dependencies', 'type': 'task_list'},
            'dependents': {'name': 'Dependents', 'type': 'task_list'},
            'attachments': {'name': 'Attachments', 'type': 'attachment_list'},
            'comments': {'name': 'Comments', 'type': 'comment_list'},
            'subtasks': {'name': 'Subtasks', 'type': 'task_list'},
            'custom_field_settings': {'name': 'Custom Field Settings', 'type': 'custom_field_settings'}
        }
        
        # Combine all fields
        all_fields = {}
        
        # Add default fields
        for field_id, field_info in default_fields.items():
            all_fields[field_id] = field_info
        
        # Add custom fields with their details
        for field in custom_fields:
            field_id = field['gid']
            field_name = field['name']
            field_type = field.get('resource_type')
            
            all_fields[field_id] = {
                'name': field_name,
                'type': field_type,
                'description': field.get('description', ''),
                'options': field.get('enum_options', [])  # For enum fields
            }
        
        # Store and return fields
        available_fields['asana'] = all_fields
        return jsonify({
            'fields': all_fields,
            'required': ['name', 'notes', 'status', 'priority', 'assignee'],
            'field_types': {
                'text': 'Text Field',
                'enum': 'Dropdown',
                'user': 'User Picker',
                'user_list': 'User List',
                'date': 'Date Picker',
                'time': 'Time Picker',
                'boolean': 'Checkbox',
                'custom': 'Custom Field',
                'workspace': 'Workspace Picker',
                'team': 'Team Picker',
                'task': 'Task Picker',
                'task_list': 'Task List',
                'attachment_list': 'Attachment List',
                'comment_list': 'Comment List',
                'project_list': 'Project List'
            }
        })
    except Exception as e:
        app.logger.error(f'Error getting Asana fields: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/test_fields', methods=['GET'])
def test_fields():
    try:
        # Get available fields from Jira
        jira_fields = jira_client.fields()
        jira_field_options = [{
            'id': field['id'],
            'name': field['name']
        } for field in jira_fields]

        # Get available fields from Asana
        asana_fields = []
        for project in asana_client.projects.find_all():
            custom_fields = asana_client.custom_fields.find_by_project(project['gid'])
            for field in custom_fields:
                asana_fields.append({
                    'id': field['gid'],
                    'name': field['name']
                })

        return jsonify({
            'jira_fields': jira_field_options,
            'asana_fields': asana_fields
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
