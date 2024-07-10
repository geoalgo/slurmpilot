import pprint
import time

from slurmpilot.config import Config


class SlurmSchedulerCallbackInterface:
    def on_job_scheduled_start(self, cluster: str, jobname: str):
        raise NotImplementedError()

    def on_established_connection(self, cluster: str):
        raise NotImplementedError()

    def on_sending_artifact(self, localpath: str, remotepath: str, cluster: str):
        raise NotImplementedError()

    def on_job_submitted_to_slurm(self, jobid: int, jobname: str):
        raise NotImplementedError()

class SlurmSchedulerCallback(SlurmSchedulerCallbackInterface):
    def __init__(self):
        self.format_pattern = "0;30;34"

    def format(self, s):
        return f'\x1b[{self.format_pattern}m{s}\x1b[0m'

    def on_job_scheduled_start(self, cluster: str, jobname: str):
        print(self.format(f"Starting job {jobname} on {cluster}."))

    def on_establishing_connection(self, cluster: str):
        print(self.format(f"Establishing ssh connection with {cluster}."))

    def on_sending_artifact(self, localpath: str, remotepath: str, cluster: str):
        print(self.format(f"Sending job data from {localpath} to {cluster}:{remotepath}."))

    def on_job_submitted_to_slurm(self, jobid: int, jobname: str):
        print(self.format(f"Job submitted to Slurm with the following id {jobid} saving the jobid locally."))

    def on_suggest_command_before_wait_completion(self, jobname: str):
        log_cmd = f"* to show the log of your job: `slurmpilot --log {jobname}`"
        sync_cmd = f"* to sync the artifact of your job: `slurmpilot --sync {jobname}`"
        status_cmd = f"* to show the status of your job: `slurmpilot --status {jobname}`"
        stop_cmd = f"* to stop your job: `slurmpilot --stop {jobname}`"
        cmds = "\n".join([log_cmd, sync_cmd, status_cmd, stop_cmd])
        print(self.format(f"You can use the following commands in a terminal:\n{cmds}"))

    def on_waiting_completion(self, jobname: str, status: str, n_seconds_wait: int):
        # TODO dependency inversion to support rich
        print(self.format(f"{jobname} status {status}, waiting {n_seconds_wait}s"))

    def on_config_loaded(self, config: Config):
        print(self.format(f"Cluster configurations loaded:"))
        for cluster, cluster_config in config.cluster_configs.items():
            print(self.format(cluster_config))


if __name__ == '__main__':

    def print_format_table():
        """
        prints table of formatted text format options
        """
        for style in range(8):
            for fg in range(30, 38):
                s1 = ''
                for bg in range(30, 48):
                    format = ';'.join([str(style), str(fg), str(bg)])
                    s1 += '\x1b[%sm %s \x1b[0m' % (format, format)
                print(s1)
            print('\n')
    print_format_table()

    print('\x1b[0;31;40m' + 'Success!' + '\x1b[0m' + "yop")

    cb = SlurmSchedulerCallback()
    cluster = "bigcluster"
    jobname = "smalljob"
    cb.on_job_scheduled_start(cluster=cluster, jobname=jobname)
    cb.on_establishing_connection(cluster=cluster)
    cb.on_sending_artifact(cluster=cluster, localpath="foo/", remotepath="foo2/")
    cb.on_job_submitted_to_slurm(jobname=jobname, jobid=12)
    for _ in range(20):
        cb.on_waiting_completion(jobname=jobname, status="PENDING", n_seconds_wait=1)
        time.sleep(0.2)
