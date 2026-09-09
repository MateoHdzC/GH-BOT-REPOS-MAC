"""Git management layer executing localized Git operations via CLI with error classification."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from src.git.models import CommitInfo, GitCommandResult, GitErrorType, GitStatusSummary
from src.utils.constants import DEFAULT_COMMIT_MESSAGE, DEFAULT_REMOTE
from src.utils.logger import get_logger

logger = get_logger("git")


class GitManager:
    """Encapsulates safe execution of Git commands for a localized repository."""

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def _run_command(
        self,
        args: list[str],
        cwd: Path,
        env: Optional[dict[str, str]] = None,
    ) -> GitCommandResult:
        """Executes a git command inside the given repository directory."""
        if not cwd.exists() or not cwd.is_dir():
            return GitCommandResult(
                success=False,
                returncode=-1,
                error_message=f"Directory does not exist: {cwd}",
                error_type=GitErrorType.LOCAL_REPO_INVALID,
            )

        cmd = ["git"] + args
        merged_env = os.environ.copy()
        current_path = merged_env.get("PATH", "")
        for std_path in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]:
            if std_path not in current_path.split(":"):
                current_path = f"{std_path}:{current_path}" if current_path else std_path
        merged_env["PATH"] = current_path
        if env:
            merged_env.update(env)

        try:
            process = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=merged_env,
                check=False,
            )
            success = process.returncode == 0
            stderr_cleaned = process.stderr.strip()
            return GitCommandResult(
                success=success,
                stdout=process.stdout.strip(),
                stderr=stderr_cleaned,
                returncode=process.returncode,
                error_message=None if success else (stderr_cleaned or f"Exit code {process.returncode}"),
            )
        except subprocess.TimeoutExpired as err:
            logger.error(f"[GIT] [ERROR] Command '{' '.join(args)}' timed out in {cwd}: {err}")
            return GitCommandResult(
                success=False,
                returncode=-1,
                error_message=f"Command timed out after {self.timeout_seconds}s",
                error_type=GitErrorType.COMMAND_TIMEOUT,
            )
        except FileNotFoundError:
            logger.error("[GIT] [ERROR] Git binary was not found on system PATH.")
            return GitCommandResult(
                success=False,
                returncode=-1,
                error_message="Git executable not found on system PATH",
                error_type=GitErrorType.LOCAL_REPO_INVALID,
            )
        except Exception as err:
            logger.error(f"[GIT] [ERROR] Unexpected error executing git {' '.join(args)} in {cwd}: {err}")
            return GitCommandResult(
                success=False,
                returncode=-1,
                error_message=str(err),
                error_type=GitErrorType.UNKNOWN,
            )

    def is_git_repo(self, repo_path: Path) -> bool:
        """Checks if the given path is a valid Git repository."""
        resolved = repo_path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            return False

        git_entry = resolved / ".git"
        if git_entry.exists() and (git_entry.is_dir() or git_entry.is_file()):
            return True

        result = self._run_command(["rev-parse", "--is-inside-work-tree"], cwd=resolved)
        return result.success and result.stdout.lower() == "true"

    def init_repo(self, repo_path: Path) -> GitCommandResult:
        """Initializes a new Git repository in the specified directory (git init)."""
        resolved = repo_path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            return GitCommandResult(
                success=False,
                returncode=-1,
                error_message=f"Directory does not exist: {resolved}",
                error_type=GitErrorType.LOCAL_REPO_INVALID,
            )
        logger.info(f"[GIT] Initializing new Git repository at {resolved}")
        return self._run_command(["init"], cwd=resolved)

    def get_current_branch(self, repo_path: Path) -> Optional[str]:
        """Returns the active branch name, or None if detached or failed."""
        result = self._run_command(["branch", "--show-current"], cwd=repo_path)
        if result.success and result.stdout:
            return result.stdout.strip()
        result_rev = self._run_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
        if result_rev.success and result_rev.stdout != "HEAD":
            return result_rev.stdout.strip()
        return None

    def get_remotes(self, repo_path: Path) -> list[str]:
        """Returns a list of configured remote names for the repository."""
        resolved = repo_path.expanduser().resolve()
        result = self._run_command(["remote"], cwd=resolved)
        if result.success and result.stdout:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return []

    def get_remote_url(self, repo_path: Path, remote_name: str = DEFAULT_REMOTE) -> Optional[str]:
        """Gets the configured remote fetch/push URL for the given remote name."""
        resolved = repo_path.expanduser().resolve()
        result = self._run_command(["remote", "get-url", remote_name], cwd=resolved)
        if result.success and result.stdout:
            return result.stdout.strip()
        result_cfg = self._run_command(["config", "--get", f"remote.{remote_name}.url"], cwd=resolved)
        if result_cfg.success and result_cfg.stdout:
            return result_cfg.stdout.strip()
        return None

    def set_remote_url(
        self, repo_path: Path, url: str, remote_name: str = DEFAULT_REMOTE
    ) -> GitCommandResult:
        """Sets or updates the remote URL for a given repository."""
        resolved = repo_path.expanduser().resolve()
        clean_url = url.strip()
        if not clean_url:
            return GitCommandResult(
                success=False,
                returncode=-1,
                error_message="Remote URL cannot be empty.",
                error_type=GitErrorType.REMOTE_NOT_FOUND,
            )

        remotes = self.get_remotes(resolved)
        if remote_name in remotes:
            logger.info(f"[GIT] Updating remote '{remote_name}' URL to {clean_url} in {resolved}")
            return self._run_command(["remote", "set-url", remote_name, clean_url], cwd=resolved)
        else:
            logger.info(f"[GIT] Adding remote '{remote_name}' with URL {clean_url} in {resolved}")
            return self._run_command(["remote", "add", remote_name, clean_url], cwd=resolved)

    def get_last_commit_info(self, repo_path: Path) -> Optional[CommitInfo]:
        """Retrieves metadata of the most recent commit on the active branch."""
        resolved = repo_path.expanduser().resolve()
        result = self._run_command(
            ["log", "-1", "--pretty=format:%H%x00%s%x00%an%x00%cI"],
            cwd=resolved,
        )
        if not result.success or not result.stdout:
            return None

        parts = result.stdout.split("\x00")
        if len(parts) >= 4:
            return CommitInfo(
                hash=parts[0],
                message=parts[1],
                author=parts[2],
                timestamp=parts[3],
            )
        return None

    def get_status(self, repo_path: Path) -> GitStatusSummary:
        """Retrieves a comprehensive summary of the working tree status."""
        resolved = repo_path.expanduser().resolve()
        if not self.is_git_repo(resolved):
            return GitStatusSummary(is_git_repo=False)

        branch = self.get_current_branch(resolved)
        remotes = tuple(self.get_remotes(resolved))
        result = self._run_command(["status", "--porcelain"], cwd=resolved)

        if not result.success:
            return GitStatusSummary(
                is_git_repo=True,
                current_branch=branch,
                remotes=remotes,
                raw_status=result.stderr,
            )

        raw = result.stdout
        if not raw:
            return GitStatusSummary(
                is_git_repo=True,
                has_changes=False,
                current_branch=branch,
                remotes=remotes,
                raw_status="",
            )

        staged_count = 0
        unstaged_count = 0
        untracked_count = 0

        for line in raw.splitlines():
            if len(line) < 2:
                continue
            index_status = line[0]
            worktree_status = line[1]

            if index_status == "?" and worktree_status == "?":
                untracked_count += 1
            else:
                if index_status not in (" ", "?"):
                    staged_count += 1
                if worktree_status not in (" ", "?"):
                    unstaged_count += 1

        has_changes = (staged_count + unstaged_count + untracked_count) > 0
        return GitStatusSummary(
            is_git_repo=True,
            has_changes=has_changes,
            staged_files_count=staged_count,
            unstaged_files_count=unstaged_count,
            untracked_files_count=untracked_count,
            current_branch=branch,
            remotes=remotes,
            raw_status=raw,
        )

    def has_changes(self, repo_path: Path) -> bool:
        """Quickly checks if there are any working tree or staged changes."""
        status = self.get_status(repo_path)
        return status.has_changes

    def stage_all(self, repo_path: Path) -> GitCommandResult:
        """Stages all working directory modifications and untracked files (git add .)."""
        resolved = repo_path.expanduser().resolve()
        logger.debug(f"[GIT] Staging all changes in {resolved}")
        return self._run_command(["add", "."], cwd=resolved)

    def has_staged_changes(self, repo_path: Path) -> bool:
        """Checks if there are differences staged in the index ready to be committed."""
        resolved = repo_path.expanduser().resolve()
        result = self._run_command(["diff", "--cached", "--quiet"], cwd=resolved)
        return result.returncode == 1

    def commit(
        self,
        repo_path: Path,
        message: str = DEFAULT_COMMIT_MESSAGE,
    ) -> GitCommandResult:
        """Creates a Git commit with the provided message if staged changes exist."""
        resolved = repo_path.expanduser().resolve()

        if not self.has_staged_changes(resolved):
            logger.info(f"[GIT] [COMMIT] Skipping commit in {resolved}: no staged changes found.")
            return GitCommandResult(
                success=True,
                stdout="Nothing to commit, working tree clean",
                error_message=None,
            )

        clean_message = message.strip() or DEFAULT_COMMIT_MESSAGE
        logger.info(f"[GIT] [COMMIT] Creating commit in {resolved}: '{clean_message}'")
        return self._run_command(["commit", "-m", clean_message], cwd=resolved)

    def classify_push_error(self, stderr: str, returncode: int) -> GitErrorType:
        """Classifies stderr output from git push into standard failure categories."""
        lower_err = stderr.lower()

        if "does not appear to be a git repository" in lower_err or "no such remote" in lower_err:
            return GitErrorType.REMOTE_NOT_FOUND
        if "permission denied" in lower_err or "authentication failed" in lower_err or "invalid username or token" in lower_err or "terminal prompts disabled" in lower_err:
            return GitErrorType.AUTH_FAILED
        if "rpc failed" in lower_err or "http 400" in lower_err or "could not resolve host" in lower_err or "connection refused" in lower_err or "network is unreachable" in lower_err or "connection timed out" in lower_err or "hung up unexpectedly" in lower_err:
            return GitErrorType.NETWORK_ERROR
        if "[rejected]" in lower_err or "non-fast-forward" in lower_err or "fetch first" in lower_err:
            return GitErrorType.REJECTED_NON_FAST_FORWARD
        if "conflict" in lower_err or "divergent branches" in lower_err:
            return GitErrorType.CONFLICT
        if "src refspec" in lower_err or "does not match any" in lower_err:
            return GitErrorType.BRANCH_NOT_FOUND

        return GitErrorType.UNKNOWN

    def push(
        self,
        repo_path: Path,
        remote: str = DEFAULT_REMOTE,
        branch: Optional[str] = None,
        token: Optional[str] = None,
        username: Optional[str] = None,
    ) -> GitCommandResult:
        """Pushes committed changes to the upstream remote repository.

        Safely handles errors without ever attempting forced pushes or destructive commands.
        """
        resolved = repo_path.expanduser().resolve()

        remotes = self.get_remotes(resolved)
        if not remotes:
            err_msg = f"Repository has no configured remotes. Cannot push to '{remote}'."
            logger.warning(f"[GIT] [PUSH] [ERROR] {err_msg} ({resolved})")
            return GitCommandResult(
                success=False,
                returncode=-1,
                error_message=err_msg,
                error_type=GitErrorType.NO_REMOTE,
            )

        if remote not in remotes:
            err_msg = f"Remote '{remote}' does not exist. Available remotes: {', '.join(remotes)}"
            logger.warning(f"[GIT] [PUSH] [ERROR] {err_msg} ({resolved})")
            return GitCommandResult(
                success=False,
                returncode=-1,
                error_message=err_msg,
                error_type=GitErrorType.REMOTE_NOT_FOUND,
            )

        target_branch = branch or self.get_current_branch(resolved) or "main"
        
        extra_args: list[str] = [
            "-c",
            "http.postBuffer=524288000",
            "-c",
            "http.maxRequestBuffer=524288000",
        ]
        if token and username:
            import base64
            auth_str = f"{username}:{token}"
            encoded = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            extra_args.extend(["-c", f"http.extraHeader=AUTHORIZATION: basic {encoded}"])

        cmd = extra_args + ["push", "-u", remote, target_branch]

        logger.info(f"[GIT] [PUSH] Pushing changes for {resolved} to {remote} (branch: {target_branch})")
        result = self._run_command(cmd, cwd=resolved)

        if result.success:
            logger.info(f"[GIT] [PUSH] Push completed successfully for {resolved}")
            return result

        error_type = self.classify_push_error(result.stderr, result.returncode)
        logger.warning(
            f"[GIT] [PUSH] [ERROR] Push failed for {resolved} (Type: {error_type.value}): {result.error_message}"
        )
        return GitCommandResult(
            success=False,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            error_message=result.error_message,
            error_type=error_type,
        )
