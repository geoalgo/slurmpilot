from fabric import Connection
user="fr_ds1228"
conn = Connection("horeka", user="fr_ds1228")
conn.run("ls")