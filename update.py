import json
import datetime
import subprocess


def get_github_username():
    try:
        # Get current GitHub user info using GitHub CLI
        result = subprocess.run(['gh', 'api', 'user'], capture_output=True, text=True, check=True)
        user_data = json.loads(result.stdout)
        return user_data.get('login')  # 'login' is the username in GitHub's API
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        # Fall back to a default if anything goes wrong
        return "fallback-user"


# Step 1: Checkout or create the local branch
def checkout_or_create_local_branch():
    # Get GitHub username and append '-local'
    github_username = get_github_username()
    branch = f"{github_username}-local"

    # Check if the branch exists
    branches = subprocess.run(['git', 'branch'], stdout=subprocess.PIPE, text=True).stdout

    if branch not in branches:
        # Create the 'local' branch if it doesn't exist
        subprocess.run(['git', 'checkout', '-b', branch], check=True)
        print("Created and checked out the '" + branch + "' branch.")
    else:
        # Checkout the 'local' branch
        subprocess.run(['git', 'checkout', branch], check=True)
        print("Checked out the '" + branch + "' branch.")

    return branch


# Step 2: Commit the new files
def commit_changes(timestamp):
    # Check if there are any changes to commit
    result = subprocess.run(['git', 'status', '--porcelain'], stdout=subprocess.PIPE, text=True)
    if not result.stdout.strip():
        print("No changes to commit.")
        return False

    # Proceed to commit changes
    subprocess.run(['git', 'add', '.'], check=True)
    subprocess.run(['git', 'commit', '-m', 'Add new notes - ' + timestamp], check=True)
    print("Changes committed successfully.")
    return True


def check_pull_request_exists(branch_name):
    """Check if a pull request already exists for the given branch."""
    try:
        # Use 'gh pr list' to check if a PR exists for this branch
        result = subprocess.run(
            ['gh', 'pr', 'list', '--head', branch_name, '--state', 'open', '--json', 'number'],
            check=True, capture_output=True, text=True
        )
        # Parse the JSON output to see if any PRs were found
        prs = json.loads(result.stdout)
        return len(prs) > 0, prs
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error checking for existing pull request: {e}")
        return False, []


# Step 3: Create a new pull request
def create_pull_request(branch_name):
    exists, prs = check_pull_request_exists(branch_name)

    if exists:
        print(f"Pull request already exists for branch {branch_name}.")
        return

    subprocess.run(
        ['gh', 'pr', 'create', '--title', f'Automated update: {branch_name}', '--body', 'This PR adds new notes.'],
        check=True)


# Step 4: Check for conflicts and merge the pull request if safe
def check_and_merge_pull_request(branch_name):
    import json

    try:
        # First, check if the current user has permission to merge pull requests
        permission_check = subprocess.run(
            ['gh', 'api', 'user', '--jq', '.login'],
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )
        current_username = permission_check.stdout.strip()

        # Get the repository name
        repo_info = subprocess.run(
            ['gh', 'repo', 'view', '--json', 'nameWithOwner'],
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )

        repo_data = json.loads(repo_info.stdout)
        repo_name = repo_data['nameWithOwner']

        # Check user permissions
        user_permission = subprocess.run(
            ['gh', 'api', f'repos/{repo_name}/collaborators/{current_username}/permission', '--jq', '.permission'],
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )
        permission_level = user_permission.stdout.strip().lower()

        # Check if user has write or admin permissions
        can_merge = permission_level in ['admin', 'write']

        if not can_merge:
            print(
                f"You don't have permission to merge pull requests in this repository. Your permission level: {permission_level}")
            return

        # Rest of the original function code for checking and merging PRs
        # Get the PR number for the branch
        pr_info = subprocess.run(
            ['gh', 'pr', 'list', '--head', branch_name, '--json', 'number'],
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )

        # Parse the JSON output to get the PR number
        pr_data = json.loads(pr_info.stdout)

        if not pr_data:
            print(f"No pull request found for branch {branch_name}")
            return

        pr_number = pr_data[0]['number']

        # Check if the PR has conflicts
        pr_check = subprocess.run(
            ['gh', 'pr', 'view', str(pr_number), '--json', 'mergeable'],
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )

        pr_check_data = json.loads(pr_check.stdout)

        # If the PR is mergeable, merge it
        if pr_check_data.get('mergeable', False):
            subprocess.run(
                ['gh', 'pr', 'merge', str(pr_number), '--merge'],
                check=True
            )
            print(f"Pull request #{pr_number} has been automatically merged.")
        else:
            # Enable auto-merge for the pull request
            try:
                subprocess.run(
                    ['gh', 'pr', 'merge', str(pr_number), '--merge', '--auto'],
                    check=True
                )
                print(
                    f"Auto-merge enabled for pull request #{pr_number}. It will be merged automatically when conflicts are resolved.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to enable auto-merge for pull request #{pr_number}: {e}")
    except subprocess.CalledProcessError as e:
        print(f"Error checking or merging the pull request: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing GitHub CLI output: {e}")
    except Exception as e:
        print(f"Unexpected error during PR merge attempt: {e}")


# Main Workflow
def main():
    try:
        branch_name = checkout_or_create_local_branch()
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

        # Commit the changes
        if not commit_changes(timestamp):
            print("No changes to push or create a pull request for. Exiting.")
            return

        # Push the branch to remote
        subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True)

        # Create a pull request
        create_pull_request(branch_name)

        # Check for conflicts and merge the pull request if possible
        check_and_merge_pull_request(branch_name)

        print("Done!")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
