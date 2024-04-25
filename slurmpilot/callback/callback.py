import time


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
    def on_waiting_completion(self, jobname: str, status: str, n_seconds_wait: int):
        # TODO dependency inversion to support rich
        return print(self.format(f"{jobname} status {status}, waiting {n_seconds_wait}s"))

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
