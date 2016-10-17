#!/usr/bin/env python

import sys,math,optparse,shutil,datetime,os.path

# Import third-party modules
import numpy
import pylab,matplotlib.cm

import client.run,client.gotmcontroller

import netCDF4

parser = optparse.OptionParser()
parser.add_option('--database',type='string',help='Path to database (SQLite only)')
parser.add_option('-r', '--rank',  type='int',   help='Rank of the result to plot (default = 1, i.e., the very best result)')
parser.add_option('-d', '--depth', type='float', help='Depth range to show (> 0)')
parser.add_option('-g', '--grid',  action='store_true', help='Whether to grid the observations.')
parser.add_option('--savenc',      type='string', help='Path to copy NetCDF output file to.')
parser.add_option('--simulationdir',type='string', help='Directory to run simulation in.')
parser.set_defaults(rank=1,depth=None,grid=False,savenc=None,simulationdir=None)
(options, args) = parser.parse_args()

if len(args)<1:
    print 'This script takes one required argument: path to job configuration file (xml).'
    sys.exit(2)
jobid = os.path.splitext(os.path.basename(args[0]))[0]

if options.depth is not None and options.depth<0:
    print 'Depth argument must be positive, but is %.6g.' % options.depth
    sys.exit(2)

extravars = ()
#extravars = (('nuh',True),)
#extravars = [('mean_1',False),('mean_2',False),('var_1_1',False),('var_2_2',False),('cor_2_1',False)]
#extravars = (('phytosize_mean_om',False),('phytosize_var_om',False))

if options.database is None:
   import mysqlinfo
   db = mysqlinfo.connect(mysqlinfo.select)
else:
   import sqlite3
   db = sqlite3.connect(options.database)

# Connect to database and retrieve best parameter set.
c = db.cursor()
query = "SELECT `parameters`,`lnlikelihood` FROM `runs`,`results` WHERE `runs`.`id`=`results`.`run` AND `runs`.`job`='%s'" % jobid
c.execute(query)
res = [(strpars,lnlikelihood) for strpars,lnlikelihood in c if lnlikelihood is not None]

# Initialize the GOTM controller.
job = client.run.getJob(args[0],simulationdir=options.simulationdir)
job.initialize()

res.sort(cmp=lambda x,y: cmp(x[1],y[1]))
parameters,lnl = res[-options.rank]
parameters = map(float,parameters.split(';'))


# Show best parameter set
print '%ith best parameter set:' % options.rank
parameters_utf = job.controller.untransformParameterValues(parameters)
for i,val in enumerate(parameters_utf):
    pi = job.controller.externalparameters[i]
    print '   %s = %.6g' % (pi['name'],val)
print 'ln likelihood = %.8g' % lnl

# Build a list of all NetCDF variables that we want model results for.
obsinfo = job.observations
outputvars = [oi['outputvariable'] for oi in obsinfo]
for vardata in extravars:
    if isinstance(vardata,basestring):
        outputvars.append(vardata)
    else:
        outputvars.append(vardata[0])

# Run and retrieve results.
#returncode = job.controller.run(parameters,showoutput=True)
#if returncode!=0:
#    print 'GOTM run failed - exiting.'
#    sys.exit(1)
#nc = NetCDFFile(ncpath,'r')
#res = job.controller.getNetCDFVariables(nc,outputvars,addcoordinates=True)
#nc.close()
likelihood,model_values = job.evaluateFitness(parameters,return_model_values=True,show_output=True)

# # Copy NetCDF file
# if options.savenc is not None:
#     print 'Saving NetCDF output to %s...' % options.savenc,
#     shutil.copyfile(ncpath,options.savenc)
#     fout = open('%s.info' % options.savenc,'w')
#     fout.write('job %i, %ith best parameter set\n' % (jobid,options.rank))
#     fout.write('%s\n' % datetime.datetime.today().isoformat())
#     fout.write('parameter values:\n')
#     for i,val in enumerate(parameters_utf):
#         pi = job.controller.externalparameters[i]
#         fout.write('  %s = %.6g\n' % (pi['name'],val))
#     fout.write('ln likelihood = %.8g\n' % lnl)
#     fout.close()
#     print ' done'

hres = pylab.figure(figsize=(10,9))
herr = pylab.figure()
hcor = pylab.figure(figsize=(2.5,9))
nrow = int(round(math.sqrt(len(obsinfo))))
ncol = int(math.ceil(len(obsinfo)/float(nrow)))
for i,(oi,(t_interfaces,z_interfaces,all_model_data,model_data)) in enumerate(zip(obsinfo,model_values)):
    times,observed_values,zs = oi['times'],oi['values'],oi['zs']

    modelmin = oi.get('modelminimum',None)
    if modelmin is not None:
        all_model_data[modeldata<modelmin] = modelmin
        model_data[modeldata<modelmin] = modelmin

    # If we do a relative fit, scale the model result to best match observations.
    if oi['relativefit']:
        if (model_data==0.).all():
            print 'ERROR: cannot calculate optimal scaling factor for %s because all model values equal zero.' % oi['outputvariable']
            sys.exit(1)
        scale = (observed_values*model_data).sum()/(model_data**2).sum()
        print 'Optimal model-to-observation scaling factor for %s = %.6g.' % (oi['outputvariable'],scale)
        model_data *= scale
        all_model_data *= scale
    elif oi['fixed_scale_factor'] is not None:
        model_data *= oi['fixed_scale_factor']
        all_model_data *= oi['fixed_scale_factor']

    zmin,zmax = z_interfaces[:,0].min(),z_interfaces[:,-1].max()
    z_centres = (z_interfaces[:-1,:-1] + z_interfaces[1:,:-1] + z_interfaces[:-1,1:] + z_interfaces[1:,1:])/4
    if options.depth is not None: zmin= -options.depth

    valid_obs = zs>zmin
    valid_mod = z_centres>zmin
    varrange = (min(all_model_data[valid_mod].min(),observed_values[valid_obs].min()),max(all_model_data[valid_mod].max(),observed_values[valid_obs].max()))

    # Create figure for model-data comparison
    pylab.figure(hres.number)

    # Plot model result
    t_interfaces = pylab.date2num(t_interfaces)
    pylab.subplot(len(obsinfo),2,i*2+1)
    pc = pylab.pcolormesh(t_interfaces,z_interfaces,all_model_data)
    pylab.clim(varrange)
    pylab.ylim(zmin,zmax)
    pylab.colorbar(pc)
    pylab.xlim(t_interfaces[0,0],t_interfaces[-1,0])
    xax = pylab.gca().xaxis
    loc = matplotlib.dates.AutoDateLocator()
    xax.set_major_formatter(matplotlib.dates.AutoDateFormatter(loc))
    xax.set_major_locator(loc)
    pylab.grid(True)

    # Plot observations
    pylab.subplot(len(obsinfo),2,i*2+2)
    numtimes = pylab.date2num(times)
    if options.grid:
        import matplotlib.mlab
        gridded_observed_values = matplotlib.mlab.griddata(numtimes,zs,observed_values,t_interfaces,z_interfaces,'linear')
        pylab.pcolormesh(t_interfaces,z_interfaces,gridded_observed_values)
    else:
        pylab.scatter(numtimes,zs,s=10,c=observed_values,cmap=matplotlib.cm.jet,vmin=varrange[0],vmax=varrange[1],edgecolors='none')
    pylab.ylim(zmin,zmax)
    pylab.xlim(t_interfaces[0,0],t_interfaces[-1,0])
    pylab.clim(varrange)
    xax = pylab.gca().xaxis
    loc = matplotlib.dates.AutoDateLocator()
    xax.set_major_formatter(matplotlib.dates.AutoDateFormatter(loc))
    xax.set_major_locator(loc)
    pylab.grid(True)

    # Plot model predictions vs. observations
    pylab.figure(hcor.number)
    #pylab.subplot(nrow,ncol,i+1)
    pylab.subplot(len(obsinfo),1,i+1)
    pylab.plot(observed_values,model_data,'.')
    pylab.grid(True)
    mi,ma = min(observed_values.min(),model_data.min()),max(observed_values.max(),model_data.max())
    pylab.xlim(mi,ma)
    pylab.ylim(mi,ma)
    pylab.hold(True)
    pylab.plot((mi,ma),(mi,ma),'-k')
    pylab.xlabel('observation')
    pylab.ylabel('model')

    # Plot histogram with errors.
    pylab.figure(herr.number)
    pylab.subplot(len(obsinfo),1,i+1)
    diff = model_data-observed_values
    var_obs = ((observed_values-observed_values.mean())**2).mean()
    var_mod = ((model_data-model_data.mean())**2).mean()
    cov = ((observed_values-observed_values.mean())*(model_data-model_data.mean())).mean()
    cor = cov/numpy.sqrt(var_obs*var_mod)
    #pylab.plot(diff,obs[:,1],'o')
    #pylab.figure()
    n, bins, patches = pylab.hist(diff, 100, normed=1)
    pylab.xlabel('model - observation')
    print '%s: mean absolute error = %.4g, rmse = %.4g., cor = %.4g, s.d. mod = %.4g, s.d. obs = %.4g' % (oi['outputvariable'],numpy.mean(numpy.abs(diff)),numpy.sqrt(numpy.mean(diff**2)),cor,numpy.sqrt(var_mod),numpy.sqrt(var_obs))
    #y = pylab.normpdf(bins, 0., numpy.sqrt(ssq/len(diff)))
    #l = pylab.plot(bins, y, 'r--', linewidth=2)

if len(extravars)>0:
    pylab.figure()
    varcount = float(len(extravars))
    rowcount = int(math.ceil(math.sqrt(varcount)))
    colcount = int(math.ceil(varcount/rowcount))
    for i,vardata in enumerate(extravars):
        if isinstance(vardata,basestring):
            varname = vardata
            logscale = False
        else:
            varname = vardata[0]
            logscale = vardata[1]
        modeldata = res[varname]
        if logscale: modeldata = numpy.log10(modeldata)
        pylab.subplot(rowcount,colcount,i+1)
        pylab.pcolormesh(tim_stag,z_stag,modeldata.transpose())
        pylab.ylim(-viewdepth,0)
        pylab.colorbar()
        xax = pylab.gca().xaxis
        loc = matplotlib.dates.AutoDateLocator()
        xax.set_major_formatter(matplotlib.dates.AutoDateFormatter(loc))
        xax.set_major_locator(loc)
        pylab.grid(True)

pylab.show()
