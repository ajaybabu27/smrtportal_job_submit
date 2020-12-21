import re
import subprocess
import os
import sys
#import urllib2
import mysql.connector

def get_jobs(pp_path):
	pattern = re.compile("^[A-Za-z]{2}[0-9]{6}_[A-Za-z]{2}_[0-9]{5}_[0-9][A-Za-z]")
	#table = urllib2.urlopen("http://sebrar01-2.hpc.mssm.edu:8585/smrtportal/api/jobs/csv?options=%7B%22rows%22%3A5000%2C%22page%22%3A1%2C%22sortBy%22%3A%22jobId%22%2C%22sortOrder%22%3A%22desc%22%2C%22columnNames%22%3A%5B%22jobId%22%2C%22name%22%2C%22version%22%2C%22protocolName%22%2C%22referenceSequenceName%22%2C%22automated%22%2C%22whenStarted%22%2C%22createdBy%22%2C%22groupNames%22%2C%22jobStatus%22%2C%22comments%22%2C%22sampleName%22%2C%22instrumentName%22%2C%22inputCount%22%2C%22collectionProtocol%22%2C%22primaryProtocol%22%2C%22sequencingCondition%22%2C%22plateId%22%5D%7D&status=Completed%2CFailed%2CStopped")
	table=open("jobs.csv",'r')
	table.readline()
	to_submit = set()
	jobs_run = set()
	with open('data/jobs_run') as jr:
		for line in jr:
			
			jobs_run.add(line.rstrip())
	for line in table:
		
		automated, collectionProtocol, comments, createdBy, groupNames, inputCount, instrumentName, jobId, jobStatus, \
		name, plateId, primaryProtocol, protocolName ,referenceSequenceName, sampleName, sequencingCondition, version, \
		whenStarted = line.split('","')

		#if name in ['Copy_of_ER_15402_3A_HGAP3','Copy_of_ER_15365_3A_HGAP3','Copy_of_ER_15405_3A_HGAP3']:
		#	to_submit.add((jobId, name[8:]))			

		if jobStatus == 'Completed' and not pattern.match(name) is None and not jobId in jobs_run and protocolName=='RS_HGAP_Assembly.3':
			
			to_submit.add((jobId, name))

		#if name=='ER_20265_3A_HGAP3': 		
		#	to_submit.add((jobId, name))	
			
	path = os.path.expanduser('~') + '/.my.cnf'
	with open(path) as cnf_file:
		for line in cnf_file:
			if line.startswith('user='):
				user = line.rstrip()[5:]
			if line.startswith('password='):
				pw = line.rstrip()[9:]
			if line.startswith('host='):
				host = line.rstrip()[5:]
			if line.startswith('database='):
				database = line.rstrip()[9:]

	db = mysql.connector.connect(host=host,user=user,passwd=pw,db=database)
	cur=db.cursor()	
	to_q = []
	rejected = []
	for i in to_submit:
		with open('data/jobs_run', 'a') as jr:
			jr.write(i[0] + '\n')
			 
		smrtjob, sample = i
		
		smrtjob = smrtjob.zfill(6)
		sample = sample[9:11] + sample[12:17] + '.' + sample[18:20]
		print sample
		try:
					
			cur.execute("""select STOCK_ID from tExtracts where EXTRACT_ID='""" + sample + "'")
			stock_id=str(cur.fetchone()[0])
			cur.execute("select ISOLATE_ID from tStocks where STOCK_ID='" + stock_id + "'")
			isolate_id = str(cur.fetchone()[0])
			cur.execute("select ORGANISM_ID from tIsolates where ISOLATE_ID='" + isolate_id + "'")
			organism_id =  str(cur.fetchone()[0])
			cur.execute("select abbreviated_name from tOrganisms where ORGANISM_ID='" + organism_id + "'")
			species =  str(cur.fetchone()[0])
			if species == 'MRSA' or species == 'MSSA':
				species = 'S_aureus'
		except IndexError:
			rejected.append(i[1])
			with open('data/rejected', 'a') as rejects:
				rejects.write(smrtjob + ' : ' + sample + ' not in pathogendb.\n')
			continue
		sample = sample.replace('.', '_')
		#os.system('rm -r /sc/orga/projects/InfectiousDisease/post-assembly-output/' + sample + '_' + smrtjob)
		if os.path.isdir('/sc/arion/projects/InfectiousDisease/post-assembly-output/' + sample + '_' + smrtjob):
			rejected.append(i[1])
			with open('data/rejected', 'a') as rejects:
				rejects.write(smrtjob + ' : ' + sample + ' already in post-assembly-output.\n')
			continue
        
		with open('bsubs/' + i[0] + '.bsub', 'w') as bsub:
			to_q.append(i[1])
			bsub.write('#!/bin/bash\n'
			'#BSUB -J ' + smrtjob + '\n'
			'#BSUB -P acc_InfectiousDisease\n'
			'#BSUB -q private\n'
			'#BSUB -n 12\n'
			'#BSUB -R span[hosts=1]\n'
			'#BSUB -R rusage[mem=4000]\n'
			'#BSUB -W 23:00\n'			
			'#BSUB -o %J.stdout\n'
			'#BSUB -eo %J.stderr\n'
			'#BSUB -L /bin/bash\n'
			'cd ' + pp_path + '\n'
			'./post-assemble-pathogen  OUT=/sc/arion/projects/InfectiousDisease/post-assembly-output/' + sample + '_' + smrtjob +
			' SMRT_JOB_ID=' + smrtjob + ' STRAIN_NAME=' + sample + ' SPECIES=' + species + ' LSF_DISABLED=1 CLUSTER=BASH SEQ_PLATFORM=RS2 igb_to_pathogendb\n')
		#subprocess.Popen('git add bsubs/' + i[0] + '.bsub', shell=True).wait()
		subprocess.Popen('bsub < ' + 'bsubs/' + i[0] + '.bsub', shell=True).wait()
	#if len(to_q) + len(rejected) >= 1:
	#	subprocess.Popen('git commit -m "submitting ' + str(len(to_submit)) + ' jobs. ' + ', '.join(to_q) + ' : ' + str(len(rejected)) + ' jobs not submitted."', shell=True).wait()
	#	subprocess.Popen('git push origin master', shell=True).wait()
	
	cur.close()
	db.close()
get_jobs(os.path.abspath(sys.argv[1]))
