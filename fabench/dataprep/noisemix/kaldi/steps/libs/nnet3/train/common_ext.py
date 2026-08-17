

# Copyright 2016    Vijayaditya Peddinti.
#           2016    Vimal Manohar
# Apache 2.0

"""This module contains classes and methods common to training of
nnet3 neural networks.
"""
from __future__ import division

import argparse
import glob
import logging
import os
import math
import re
import shutil

import libs.common as common_lib
from libs.nnet3.train.dropout_schedule import *

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def halve_minibatch_size_str(minibatch_size_str):
    """Halve a minibatch-size string, as would be validated by
    validate_minibatch_size_str (see docs for that).  This halves
    all the integer elements of minibatch_size_str that represent minibatch
    sizes (as opposed to chunk-lengths) and that are >1."""

    if not validate_minibatch_size_str(minibatch_size_str):
        raise Exception("Invalid minibatch-size string '{0}'".format(minibatch_size_str))

    a = minibatch_size_str.split("/")
    ans = []
    for elem in a:
        b = elem.split('=')
        # We expect b to have length 2 in the normal case.
        if len(b) == 1:
            return halve_range_str(elem)
        else:
            assert len(b) == 2
            ans.append('{0}={1}'.format(b[0], halve_range_str(b[1])))
    return '/'.join(ans)

def validate_chunk_width(chunk_width):
    """Validate a chunk-width string , returns boolean.
    Expected to be a string representing either an integer, like '20',
    or a comma-separated list of integers like '20,30,16'"""
    if not isinstance(chunk_width, str):
        return False
    a = chunk_width.split(",")
    assert len(a) != 0  # would be code error
    for elem in a:
        try:
            i = int(elem)
            if i < 1 and i != -1:
                return False
        except:
            return False
    return True

def verify_switch_ivector_egs_dir(egs_dir, feat_dim, ivector_dim, ivector_extractor_l1_id, ivector_extractor_l2_id,
                   left_context, right_context,
                   left_context_initial=-1, right_context_final=-1):
    try:
        egs_feat_dim = int(open('{0}/info/feat_dim'.format(
                                    egs_dir)).readline())

        egs_ivector_l1_id = None
        try:
            egs_ivector_l1_id = open('{0}/info/final_l1.ie.id'.format(
                                        egs_dir)).readline().strip()
            if (egs_ivector_l1_id == ""):
                egs_ivector_l1_id = None
        except:
            # it could actually happen that the file is not there
            # for example in cases where the egs were dumped by
            # an older version of the script
            pass
        
        egs_ivector_l2_id = None
        try:
            egs_ivector_l2_id = open('{0}/info/final_l2.ie.id'.format(
                                        egs_dir)).readline().strip()
            if (egs_ivector_l2_id == ""):
                egs_ivector_l2_id = None
        except:
            # it could actually happen that the file is not there
            # for example in cases where the egs were dumped by
            # an older version of the script
            pass

        try:
            egs_ivector_dim = int(open('{0}/info/ivector_dim'.format(
                egs_dir)).readline())
        except:
            egs_ivector_dim = 0
        egs_left_context = int(open('{0}/info/left_context'.format(
                                    egs_dir)).readline())
        egs_right_context = int(open('{0}/info/right_context'.format(
                                    egs_dir)).readline())
        try:
            egs_left_context_initial = int(open('{0}/info/left_context_initial'.format(
                        egs_dir)).readline())
        except:  # older scripts didn't write this, treat it as -1 in that case.
            egs_left_context_initial = -1
        try:
            egs_right_context_final = int(open('{0}/info/right_context_final'.format(
                        egs_dir)).readline())
        except:  # older scripts didn't write this, treat it as -1 in that case.
            egs_right_context_final = -1

        # if feat_dim was supplied as 0, it means the --feat-dir option was not
        # supplied to the script, so we simply don't know what the feature dim is.
        if (feat_dim != 0 and feat_dim != egs_feat_dim) or (ivector_dim != egs_ivector_dim):
            raise Exception("There is mismatch between featdim/ivector_dim of "
                            "the current experiment and the provided "
                            "egs directory")

        if (((egs_ivector_l1_id is None) and (ivector_extractor_l1_id is not None)) or
            ((egs_ivector_l1_id is not None) and (ivector_extractor_l1_id is None))):
            logger.warning("The l1 ivector ids are used inconsistently. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")
            logger.warning("ivector id for egs: {0} in dir {1}".format(egs_ivector_l1_id, egs_dir))
            logger.warning("ivector id for extractor: {0}".format(ivector_extractor_l1_id))
        elif (((egs_ivector_l2_id is None) and (ivector_extractor_l2_id is not None)) or
            ((egs_ivector_l2_id is not None) and (ivector_extractor_l2_id is None))):
            logger.warning("The l1 ivector ids are used inconsistently. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")
            logger.warning("ivector id for egs: {0} in dir {1}".format(egs_ivector_l2_id, egs_dir))
            logger.warning("ivector id for extractor: {0}".format(ivector_extractor_l2_id))
        elif ((egs_ivector_dim > 0) and (egs_ivector_l1_id is None) and (ivector_extractor_l1_id is None)):
            logger.warning("The l1 ivector ids are not used. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")
        elif ((egs_ivector_dim > 0) and (egs_ivector_l2_id is None) and (ivector_extractor_l2_id is None)):
            logger.warning("The l2 ivector ids are not used. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")    
        elif ivector_extractor_l1_id != egs_ivector_l1_id:
            raise Exception("The egs were generated using a different l1 ivector "
                            "extractor. id1 = {0}, id2={1}".format(
                                ivector_extractor_l1_id, egs_ivector_l1_id))
        elif ivector_extractor_l2_id != egs_ivector_l2_id:
            raise Exception("The egs were generated using a different l2 ivector "
                            "extractor. id1 = {0}, id2={1}".format(
                                ivector_extractor_l2_id, egs_ivector_l2_id))
        if (egs_left_context < left_context or
            egs_right_context < right_context):
            raise Exception('The egs have insufficient (l,r) context ({0},{1}) '
                            'versus expected ({2},{3})'.format(
                                egs_left_context, egs_right_context,
                                left_context, right_context))

        # the condition on the initial/final context is an equality condition,
        # not an inequality condition, as there is no mechanism to 'correct' the
        # context (by subtracting context) while copying the egs, like there is
        # for the regular left-right context.  If the user is determined to use
        # previously dumped egs, they may be able to slightly adjust the
        # --egs.chunk-left-context-initial and --egs.chunk-right-context-final
        # options to make things matched up.  [note: the model l/r context gets
        # added in, so you have to correct for changes in that.]
        if (egs_left_context_initial != left_context_initial or
            egs_right_context_final != right_context_final):
            raise Exception('The egs have incorrect initial/final (l,r) context '
                            '({0},{1}) versus expected ({2},{3}).  See code from '
                            'where this exception was raised for more info'.format(
                                egs_left_context_initial, egs_right_context_final,
                                left_context_initial, right_context_final))

        frames_per_eg_str = open('{0}/info/frames_per_eg'.format(
                             egs_dir)).readline().rstrip()
        if not validate_chunk_width(frames_per_eg_str):
            raise Exception("Invalid frames_per_eg in directory {0}/info".format(
                    egs_dir))
        num_archives = int(open('{0}/info/num_archives'.format(
                                    egs_dir)).readline())

        return [egs_left_context, egs_right_context,
                frames_per_eg_str, num_archives]
    except (IOError, ValueError):
        logger.error("The egs dir {0} has missing or "
                     "malformed files.".format(egs_dir))
        raise


def verify_switch_ivector_egs_dir_3ways(egs_dir, feat_dim, ivector_dim, ivector_extractor_l1_id, ivector_extractor_l2_id,
                   ivector_extractor_l3_id, left_context, right_context,
                   left_context_initial=-1, right_context_final=-1):
    try:
        egs_feat_dim = int(open('{0}/info/feat_dim'.format(
                                    egs_dir)).readline())

        egs_ivector_l1_id = None
        try:
            egs_ivector_l1_id = open('{0}/info/final_l1.ie.id'.format(
                                        egs_dir)).readline().strip()
            if (egs_ivector_l1_id == ""):
                egs_ivector_l1_id = None
        except:
            # it could actually happen that the file is not there
            # for example in cases where the egs were dumped by
            # an older version of the script
            pass
        
        egs_ivector_l2_id = None
        try:
            egs_ivector_l2_id = open('{0}/info/final_l2.ie.id'.format(
                                        egs_dir)).readline().strip()
            if (egs_ivector_l2_id == ""):
                egs_ivector_l2_id = None
        except:
            # it could actually happen that the file is not there
            # for example in cases where the egs were dumped by
            # an older version of the script
            pass

        egs_ivector_l3_id = None
        try:
            egs_ivector_l3_id = open('{0}/info/final_l3.ie.id'.format(
                                        egs_dir)).readline().strip()
            if (egs_ivector_l3_id == ""):
                egs_ivector_l3_id = None
        except:
            # it could actually happen that the file is not there
            # for example in cases where the egs were dumped by
            # an older version of the script
            pass

        try:
            egs_ivector_dim = int(open('{0}/info/ivector_dim'.format(
                egs_dir)).readline())
        except:
            egs_ivector_dim = 0
        egs_left_context = int(open('{0}/info/left_context'.format(
                                    egs_dir)).readline())
        egs_right_context = int(open('{0}/info/right_context'.format(
                                    egs_dir)).readline())
        try:
            egs_left_context_initial = int(open('{0}/info/left_context_initial'.format(
                        egs_dir)).readline())
        except:  # older scripts didn't write this, treat it as -1 in that case.
            egs_left_context_initial = -1
        try:
            egs_right_context_final = int(open('{0}/info/right_context_final'.format(
                        egs_dir)).readline())
        except:  # older scripts didn't write this, treat it as -1 in that case.
            egs_right_context_final = -1

        # if feat_dim was supplied as 0, it means the --feat-dir option was not
        # supplied to the script, so we simply don't know what the feature dim is.
        if (feat_dim != 0 and feat_dim != egs_feat_dim) or (ivector_dim != egs_ivector_dim):
            raise Exception("There is mismatch between featdim/ivector_dim of "
                            "the current experiment and the provided "
                            "egs directory")

        if (((egs_ivector_l1_id is None) and (ivector_extractor_l1_id is not None)) or
            ((egs_ivector_l1_id is not None) and (ivector_extractor_l1_id is None))):
            logger.warning("The l1 ivector ids are used inconsistently. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")
            logger.warning("ivector id for egs: {0} in dir {1}".format(egs_ivector_l1_id, egs_dir))
            logger.warning("ivector id for extractor: {0}".format(ivector_extractor_l1_id))
        elif (((egs_ivector_l2_id is None) and (ivector_extractor_l2_id is not None)) or
            ((egs_ivector_l2_id is not None) and (ivector_extractor_l2_id is None))):
            logger.warning("The l2 ivector ids are used inconsistently. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")
            logger.warning("ivector id for egs: {0} in dir {1}".format(egs_ivector_l2_id, egs_dir))
            logger.warning("ivector id for extractor: {0}".format(ivector_extractor_l2_id))
        elif (((egs_ivector_l3_id is None) and (ivector_extractor_l3_id is not None)) or
            ((egs_ivector_l3_id is not None) and (ivector_extractor_l3_id is None))):
            logger.warning("The l3 ivector ids are used inconsistently. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")
            logger.warning("ivector id for egs: {0} in dir {1}".format(egs_ivector_l3_id, egs_dir))
            logger.warning("ivector id for extractor: {0}".format(ivector_extractor_l3_id))
        elif ((egs_ivector_dim > 0) and (egs_ivector_l1_id is None) and (ivector_extractor_l1_id is None)):
            logger.warning("The l1 ivector ids are not used. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")
        elif ((egs_ivector_dim > 0) and (egs_ivector_l2_id is None) and (ivector_extractor_l2_id is None)):
            logger.warning("The l2 ivector ids are not used. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")
        elif ((egs_ivector_dim > 0) and (egs_ivector_l3_id is None) and (ivector_extractor_l3_id is None)):
            logger.warning("The l3 ivector ids are not used. It's your "
                          "responsibility to make sure the ivector extractor "
                          "has been used consistently")                                
        elif ivector_extractor_l1_id != egs_ivector_l1_id:
            raise Exception("The egs were generated using a different l1 ivector "
                            "extractor. id1 = {0}, id2={1}".format(
                                ivector_extractor_l1_id, egs_ivector_l1_id))
        elif ivector_extractor_l2_id != egs_ivector_l2_id:
            raise Exception("The egs were generated using a different l2 ivector "
                            "extractor. id1 = {0}, id2={1}".format(
                                ivector_extractor_l2_id, egs_ivector_l2_id))
        elif ivector_extractor_l3_id != egs_ivector_l3_id:
            raise Exception("The egs were generated using a different l3 ivector "
                            "extractor. id1 = {0}, id2={1}".format(
                                ivector_extractor_l3_id, egs_ivector_l3_id))
        if (egs_left_context < left_context or
            egs_right_context < right_context):
            raise Exception('The egs have insufficient (l,r) context ({0},{1}) '
                            'versus expected ({2},{3})'.format(
                                egs_left_context, egs_right_context,
                                left_context, right_context))

        # the condition on the initial/final context is an equality condition,
        # not an inequality condition, as there is no mechanism to 'correct' the
        # context (by subtracting context) while copying the egs, like there is
        # for the regular left-right context.  If the user is determined to use
        # previously dumped egs, they may be able to slightly adjust the
        # --egs.chunk-left-context-initial and --egs.chunk-right-context-final
        # options to make things matched up.  [note: the model l/r context gets
        # added in, so you have to correct for changes in that.]
        if (egs_left_context_initial != left_context_initial or
            egs_right_context_final != right_context_final):
            raise Exception('The egs have incorrect initial/final (l,r) context '
                            '({0},{1}) versus expected ({2},{3}).  See code from '
                            'where this exception was raised for more info'.format(
                                egs_left_context_initial, egs_right_context_final,
                                left_context_initial, right_context_final))

        frames_per_eg_str = open('{0}/info/frames_per_eg'.format(
                             egs_dir)).readline().rstrip()
        if not validate_chunk_width(frames_per_eg_str):
            raise Exception("Invalid frames_per_eg in directory {0}/info".format(
                    egs_dir))
        num_archives = int(open('{0}/info/num_archives'.format(
                                    egs_dir)).readline())

        return [egs_left_context, egs_right_context,
                frames_per_eg_str, num_archives]
    except (IOError, ValueError):
        logger.error("The egs dir {0} has missing or "
                     "malformed files.".format(egs_dir))
        raise

def compute_presoftmax_prior_scale(dir, alidir, num_jobs, run_opts,
                                   presoftmax_prior_scale_power=-0.25):

    # getting the raw pdf count
    common_lib.execute_command(
        """{command} JOB=1:{num_jobs} {dir}/log/acc_pdf.JOB.log \
                ali-to-post "ark:gunzip -c {alidir}/ali.JOB.gz|" ark:- \| \
                post-to-tacc --per-pdf=true  {alidir}/final.mdl ark:- \
                {dir}/pdf_counts.JOB""".format(command=run_opts.command,
                                               num_jobs=num_jobs,
                                               dir=dir,
                                               alidir=alidir))

    common_lib.execute_command(
        """{command} {dir}/log/sum_pdf_counts.log \
                vector-sum --binary=false {dir}/pdf_counts.* {dir}/pdf_counts \
        """.format(command=run_opts.command, dir=dir))

    for file in glob.glob('{0}/pdf_counts.*'.format(dir)):
        os.remove(file)
    pdf_counts = common_lib.read_kaldi_matrix('{0}/pdf_counts'.format(dir))[0]
    scaled_counts = smooth_presoftmax_prior_scale_vector(
        pdf_counts,
        presoftmax_prior_scale_power=presoftmax_prior_scale_power,
        smooth=0.01)

    output_file = "{0}/presoftmax_prior_scale.vec".format(dir)
    common_lib.write_kaldi_matrix(output_file, [scaled_counts])
    common_lib.force_symlink("../presoftmax_prior_scale.vec",
                             "{0}/configs/presoftmax_prior_scale.vec".format(
                                dir))


def smooth_presoftmax_prior_scale_vector(pdf_counts,
                                         presoftmax_prior_scale_power=-0.25,
                                         smooth=0.01):
    total = sum(pdf_counts)
    average_count = float(total) / len(pdf_counts)
    scales = []
    for i in range(len(pdf_counts)):
        scales.append(math.pow(pdf_counts[i] + smooth * average_count,
                               presoftmax_prior_scale_power))
    num_pdfs = len(pdf_counts)
    scaled_counts = [x * float(num_pdfs) / sum(scales) for x in scales]
    return scaled_counts


def prepare_initial_network(dir, run_opts, srand=-3, input_model=None):
    if input_model is not None:
        shutil.copy(input_model, "{0}/0.raw".format(dir))
        return
    if os.path.exists(dir+"/configs/init.config"):
        common_lib.execute_command(
            """{command} {dir}/log/add_first_layer.log \
                    nnet3-init --srand={srand} {dir}/init.raw \
                    {dir}/configs/final.config {dir}/0.raw""".format(
                        command=run_opts.command, srand=srand,
                        dir=dir))
    else:
        common_lib.execute_command(
            """{command} {dir}/log/init_model.log \
           nnet3-init --srand={srand} {dir}/configs/final.config {dir}/0.raw""".format(
                        command=run_opts.command, srand=srand,
                        dir=dir))


def get_model_combine_iters(num_iters, num_epochs,
                      num_archives, max_models_combine,
                      num_jobs_final):
    """ Figures out the list of iterations for which we'll use those models
        in the final model-averaging phase.  (note: it's a weighted average
        where the weights are worked out from a subset of training data.)"""

    approx_iters_per_epoch_final = float(num_archives) / num_jobs_final
    # Note: it used to be that we would combine over an entire epoch,
    # but in practice we very rarely would use any weights from towards
    # the end of that range, so we are changing it to use not
    # approx_iters_per_epoch_final, but instead:
    # approx_iters_per_epoch_final/2 + 1,
    # dividing by 2 to use half an epoch, and adding 1 just to make sure
    # it's not zero.

    # First work out how many iterations we want to combine over in the final
    # nnet3-combine-fast invocation.
    # The number we use is:
    # min(max(max_models_combine, approx_iters_per_epoch_final/2+1),
    #     iters/2)
    # But if this value is > max_models_combine, then the models
    # are subsampled to get these many models to combine.

    num_iters_combine_initial = min(int(approx_iters_per_epoch_final/2) + 1,
                                    int(num_iters/2))

    if num_iters_combine_initial > max_models_combine:
        subsample_model_factor = int(
            float(num_iters_combine_initial) / max_models_combine)
        num_iters_combine = num_iters_combine_initial
        models_to_combine = set(range(
            num_iters - num_iters_combine_initial + 1,
            num_iters + 1, subsample_model_factor))
        models_to_combine.add(num_iters)
    else:
        subsample_model_factor = 1
        num_iters_combine = min(max_models_combine, num_iters//2)
        models_to_combine = set(range(num_iters - num_iters_combine + 1,
                                      num_iters + 1))

    return models_to_combine


def get_current_num_jobs(it, num_it, start, step, end):
    "Get number of jobs for iteration number 'it' of range('num_it')"

    ideal = float(start) + (end - start) * float(it) / num_it
    if ideal < step:
        return int(0.5 + ideal)
    else:
        return int(0.5 + ideal / step) * step


def get_learning_rate(iter, num_jobs, num_iters, num_archives_processed,
                      num_archives_to_process,
                      initial_effective_lrate, final_effective_lrate):
    if iter + 1 >= num_iters:
        effective_learning_rate = final_effective_lrate
    else:
        effective_learning_rate = (
                initial_effective_lrate
                * math.exp(num_archives_processed
                           * math.log(float(final_effective_lrate) / initial_effective_lrate)
                           / num_archives_to_process))

    return num_jobs * effective_learning_rate


def should_do_shrinkage(iter, model_file, shrink_saturation_threshold,
                        get_raw_nnet_from_am=True):

    if iter == 0:
        return True

    if get_raw_nnet_from_am:
        output = common_lib.get_command_stdout(
            "nnet3-am-info {0} 2>/dev/null | "
            "steps/nnet3/get_saturation.pl".format(model_file))
    else:
        output = common_lib.get_command_stdout(
            "nnet3-info 2>/dev/null {0} | "
            "steps/nnet3/get_saturation.pl".format(model_file))
    output = output.strip().split("\n")
    try:
        assert len(output) == 1
        saturation = float(output[0])
        assert saturation >= 0 and saturation <= 1
    except:
        raise Exception("Something went wrong, could not get "
                        "saturation from the output '{0}' of "
                        "get_saturation.pl on the info of "
                        "model {1}".format(output, model_file))
    return saturation > shrink_saturation_threshold


def remove_nnet_egs(egs_dir):
    common_lib.execute_command("steps/nnet2/remove_egs.sh {egs_dir}".format(
            egs_dir=egs_dir))


def clean_nnet_dir(nnet_dir, num_iters, egs_dir,
                   preserve_model_interval=100,
                   remove_egs=True,
                   get_raw_nnet_from_am=True):
    try:
        if remove_egs:
            remove_nnet_egs(egs_dir)

        for iter in range(num_iters):
            remove_model(nnet_dir, iter, num_iters, None,
                         preserve_model_interval,
                         get_raw_nnet_from_am=get_raw_nnet_from_am)
    except (IOError, OSError):
        logger.error("Error while cleaning up the nnet directory")
        raise


def remove_model(nnet_dir, iter, num_iters, models_to_combine=None,
                 preserve_model_interval=100,
                 get_raw_nnet_from_am=True):
    if iter % preserve_model_interval == 0:
        return
    if models_to_combine is not None and iter in models_to_combine:
        return
    if get_raw_nnet_from_am:
        file_name = '{0}/{1}.mdl'.format(nnet_dir, iter)
    else:
        file_name = '{0}/{1}.raw'.format(nnet_dir, iter)

    if os.path.isfile(file_name):
        os.remove(file_name)


def positive_int(arg):
   val = int(arg)
   if (val <= 0):
      raise argparse.ArgumentTypeError("must be positive int: '%s'" % arg)
   return val


class CommonParser(object):
    """Parser for parsing common options related to nnet3 training.

    This argument parser adds common options related to nnet3 training
    such as egs creation, training optimization options.
    These are used in the nnet3 train scripts
    in steps/nnet3/train*.py and steps/nnet3/chain/train.py
    """

    parser = argparse.ArgumentParser(add_help=False)

    def __init__(self,
                 include_chunk_context=True,
                 default_chunk_left_context=0):
        # feat options
        self.parser.add_argument("--feat.l1-online-ivector-dir", type=str,
                                 dest='l1_online_ivector_dir', default=None,
                                 action=common_lib.NullstrToNoneAction,
                                 help="""directory with the ivectors extracted
                                 in an online fashion.""")
        self.parser.add_argument("--feat.l2-online-ivector-dir", type=str,
                                 dest='l2_online_ivector_dir', default=None,
                                 action=common_lib.NullstrToNoneAction,
                                 help="""directory with the ivectors extracted
                                 in an online fashion.""")
        self.parser.add_argument("--feat.l3-online-ivector-dir", type=str,
                                 dest='l3_online_ivector_dir', default=None,
                                 action=common_lib.NullstrToNoneAction,
                                 help="""directory with the ivectors extracted
                                 in an online fashion.""")
        self.parser.add_argument("--feat.cmvn-opts", type=str,
                                 dest='cmvn_opts', default=None,
                                 action=common_lib.NullstrToNoneAction,
                                 help="A string specifying '--norm-means' "
                                 "and '--norm-vars' values")

        # egs extraction options.  there is no point adding the chunk context
        # option for non-RNNs (by which we mean basic TDNN-type topologies), as
        # it wouldn't affect anything, so we disable them if we know in advance
        # that we're not supporting RNN-type topologies (as in train_dnn.py).
        if include_chunk_context:
            self.parser.add_argument("--egs.chunk-left-context", type=int,
                                     dest='chunk_left_context',
                                     default=default_chunk_left_context,
                                     help="""Number of additional frames of input
                                 to the left of the input chunk. This extra
                                 context will be used in the estimation of RNN
                                 state before prediction of the first label. In
                                 the case of FF-DNN this extra context will be
                                 used to allow for frame-shifts""")
            self.parser.add_argument("--egs.chunk-right-context", type=int,
                                     dest='chunk_right_context', default=0,
                                     help="""Number of additional frames of input
                                     to the right of the input chunk. This extra
                                     context will be used in the estimation of
                                     bidirectional RNN state before prediction of
                                 the first label.""")
            self.parser.add_argument("--egs.chunk-left-context-initial", type=int,
                                     dest='chunk_left_context_initial', default=-1,
                                     help="""Number of additional frames of input
                                 to the left of the *first* input chunk extracted
                                 from an utterance.  If negative, defaults to
                                 the same as --egs.chunk-left-context""")
            self.parser.add_argument("--egs.chunk-right-context-final", type=int,
                                     dest='chunk_right_context_final', default=-1,
                                     help="""Number of additional frames of input
                                 to the right of the *last* input chunk extracted
                                 from an utterance.  If negative, defaults to the
                                 same as --egs.chunk-right-context""")
        self.parser.add_argument("--egs.dir", type=str, dest='egs_dir',
                                 default=None,
                                 action=common_lib.NullstrToNoneAction,
                                 help="""Directory with egs. If specified this
                                 directory will be used rather than extracting
                                 egs""")
        self.parser.add_argument("--egs.stage", type=int, dest='egs_stage',
                                 default=0,
                                 help="Stage at which get_egs.sh should be "
                                 "restarted")
        self.parser.add_argument("--egs.opts", type=str, dest='egs_opts',
                                 default=None,
                                 action=common_lib.NullstrToNoneAction,
                                 help="""String to provide options directly
                                 to steps/nnet3/get_egs.sh script""")

        # trainer options
        self.parser.add_argument("--trainer.srand", type=int, dest='srand',
                                 default=0,
                                 help="""Sets the random seed for model
                                 initialization and egs shuffling.
                                 Warning: This random seed does not control all
                                 aspects of this experiment.  There might be
                                 other random seeds used in other stages of the
                                 experiment like data preparation (e.g. volume
                                 perturbation).""")
        self.parser.add_argument("--trainer.num-epochs", type=float,
                                 dest='num_epochs', default=8.0,
                                 help="Number of epochs to train the model")
        self.parser.add_argument("--trainer.shuffle-buffer-size", type=int,
                                 dest='shuffle_buffer_size', default=5000,
                                 help=""" Controls randomization of the samples
                                 on each iteration. If 0 or a large value the
                                 randomization is complete, but this will
                                 consume memory and cause spikes in disk I/O.
                                 Smaller is easier on disk and memory but less
                                 random.  It's not a huge deal though, as
                                 samples are anyway randomized right at the
                                 start.  (the point of this is to get data in
                                 different minibatches on different iterations,
                                 since in the preconditioning method, 2 samples
                                 in the same minibatch can affect each others'
                                 gradients.""")
        self.parser.add_argument("--trainer.max-param-change", type=float,
                                 dest='max_param_change', default=2.0,
                                 help="""The maximum change in parameters
                                 allowed per minibatch, measured in Frobenius
                                 norm over the entire model""")
        self.parser.add_argument("--trainer.samples-per-iter", type=int,
                                 dest='samples_per_iter', default=400000,
                                 help="This is really the number of egs in "
                                 "each archive.")
        self.parser.add_argument("--trainer.lda.rand-prune", type=float,
                                 dest='rand_prune', default=4.0,
                                 help="Value used in preconditioning "
                                 "matrix estimation")
        self.parser.add_argument("--trainer.lda.max-lda-jobs", type=int,
                                 dest='max_lda_jobs', default=10,
                                 help="Max number of jobs used for "
                                 "LDA stats accumulation")
        self.parser.add_argument("--trainer.presoftmax-prior-scale-power",
                                 type=float,
                                 dest='presoftmax_prior_scale_power',
                                 default=-0.25,
                                 help="Scale on presofmax prior")
        self.parser.add_argument("--trainer.optimization.proportional-shrink", type=float,
                                 dest='proportional_shrink', default=0.0,
                                 help="""If nonzero, this will set a shrinkage (scaling)
                        factor for the parameters, whose value is set as:
                        shrink-value=(1.0 - proportional-shrink * learning-rate), where
                        'learning-rate' is the learning rate being applied
                        on the current iteration, which will vary from
                        initial-effective-lrate*num-jobs-initial to
                        final-effective-lrate*num-jobs-final.
                        Unlike for train_rnn.py, this is applied unconditionally,
                        it does not depend on saturation of nonlinearities.
                        Can be used to roughly approximate l2 regularization.""")

        # Parameters for the optimization
        self.parser.add_argument(
            "--trainer.optimization.initial-effective-lrate", type=float,
            dest='initial_effective_lrate', default=0.0003,
            help="Learning rate used during the initial iteration")
        self.parser.add_argument(
            "--trainer.optimization.final-effective-lrate", type=float,
            dest='final_effective_lrate', default=0.00003,
            help="Learning rate used during the final iteration")
        self.parser.add_argument("--trainer.optimization.num-jobs-initial",
                                 type=int, dest='num_jobs_initial', default=1,
                                 help="Number of neural net jobs to run in "
                                 "parallel at the start of training")
        self.parser.add_argument("--trainer.optimization.num-jobs-final",
                                 type=int, dest='num_jobs_final', default=8,
                                 help="Number of neural net jobs to run in "
                                 "parallel at the end of training")
        self.parser.add_argument("--trainer.optimization.num-jobs-step",
            type=positive_int,  metavar='N', dest='num_jobs_step', default=1,
            help="""Number of jobs increment, when exceeds this number. For
            example, if N=3, the number of jobs may progress as 1, 2, 3, 6, 9...""")
        self.parser.add_argument("--trainer.optimization.max-models-combine",
                                 "--trainer.max-models-combine",
                                 type=int, dest='max_models_combine',
                                 default=20,
                                 help="""The maximum number of models used in
                                 the final model combination stage.  These
                                 models will themselves be averages of
                                 iteration-number ranges""")
        self.parser.add_argument("--trainer.optimization.max-objective-evaluations",
                                 "--trainer.max-objective-evaluations",
                                 type=int, dest='max_objective_evaluations',
                                 default=30,
                                 help="""The maximum number of objective
                                 evaluations in order to figure out the
                                 best number of models to combine. It helps to
                                 speedup if the number of models provided to the
                                 model combination binary is quite large (e.g.
                                 several hundred).""")
        self.parser.add_argument("--trainer.optimization.do-final-combination",
                                 dest='do_final_combination', type=str,
                                 action=common_lib.StrToBoolAction,
                                 choices=["true", "false"], default=True,
                                 help="""Set this to false to disable the final
                                 'combine' stage (in this case we just use the
                                 last-numbered model as the final.mdl).""")
        self.parser.add_argument("--trainer.optimization.combine-sum-to-one-penalty",
                                 type=float, dest='combine_sum_to_one_penalty', default=0.0,
                                 help="""This option is deprecated and does nothing.""")
        self.parser.add_argument("--trainer.optimization.momentum", type=float,
                                 dest='momentum', default=0.0,
                                 help="""Momentum used in update computation.
                                 Note: we implemented it in such a way that it
                                 doesn't increase the effective learning
                                 rate.""")
        self.parser.add_argument("--trainer.dropout-schedule", type=str,
                                 action=common_lib.NullstrToNoneAction,
                                 dest='dropout_schedule', default=None,
                                 help="""Use this to specify the dropout
                                 schedule.  You specify a piecewise linear
                                 function on the domain [0,1], where 0 is the
                                 start and 1 is the end of training; the
                                 function-argument (x) rises linearly with the
                                 amount of data you have seen, not iteration
                                 number (this improves invariance to
                                 num-jobs-{initial-final}).  E.g. '0,0.2,0'
                                 means 0 at the start; 0.2 after seeing half
                                 the data; and 0 at the end.  You may specify
                                 the x-value of selected points, e.g.
                                 '0,0.2@0.25,0' means that the 0.2
                                 dropout-proportion is reached a quarter of the
                                 way through the data.   The start/end x-values
                                 are at x=0/x=1, and other unspecified x-values
                                 are interpolated between known x-values.  You
                                 may specify different rules for different
                                 component-name patterns using 'pattern1=func1
                                 pattern2=func2', e.g. 'relu*=0,0.1,0
                                 lstm*=0,0.2,0'.  More general should precede
                                 less general patterns, as they are applied
                                 sequentially.""")
        self.parser.add_argument("--trainer.add-option", type=str,
                                 dest='train_opts', action='append', default=[],
                                 help="""You can use this to add arbitrary options that
                                 will be passed through to the core training code (nnet3-train
                                 or nnet3-chain-train)""")
        self.parser.add_argument("--trainer.optimization.backstitch-training-scale",
                                 type=float, dest='backstitch_training_scale',
                                 default=0.0, help="""scale of parameters changes
                                 used in backstitch training step.""")
        self.parser.add_argument("--trainer.optimization.backstitch-training-interval",
                                 type=int, dest='backstitch_training_interval',
                                 default=1, help="""the interval of minibatches
                                 that backstitch training is applied on.""")
        self.parser.add_argument("--trainer.compute-per-dim-accuracy",
                                 dest='compute_per_dim_accuracy',
                                 type=str, choices=['true', 'false'],
                                 default=False,
                                 action=common_lib.StrToBoolAction,
                                 help="Compute train and validation "
                                 "accuracy per-dim")

        # General options
        self.parser.add_argument("--stage", type=int, default=-4,
                                 help="Specifies the stage of the experiment "
                                 "to execution from")
        self.parser.add_argument("--exit-stage", type=int, default=None,
                                 help="If specified, training exits before "
                                 "running this stage")
        self.parser.add_argument("--cmd", type=str, dest="command",
                                 action=common_lib.NullstrToNoneAction,
                                 help="""Specifies the script to launch jobs.
                                 e.g. queue.pl for launching on SGE cluster
                                        run.pl for launching on local machine
                                 """, default="queue.pl")
        self.parser.add_argument("--egs.cmd", type=str, dest="egs_command",
                                 action=common_lib.NullstrToNoneAction,
                                 help="Script to launch egs jobs")
        self.parser.add_argument("--use-gpu", type=str,
                                 choices=["true", "false", "yes", "no", "wait"],
                                 help="Use GPU for training. "
                                 "Note 'true' and 'false' are deprecated.",
                                 default="yes")
        self.parser.add_argument("--cleanup", type=str,
                                 action=common_lib.StrToBoolAction,
                                 choices=["true", "false"], default=True,
                                 help="Clean up models after training")
        self.parser.add_argument("--cleanup.remove-egs", type=str,
                                 dest='remove_egs', default=True,
                                 action=common_lib.StrToBoolAction,
                                 choices=["true", "false"],
                                 help="If true, remove egs after experiment")
        self.parser.add_argument("--cleanup.preserve-model-interval",
                                 dest="preserve_model_interval",
                                 type=int, default=100,
                                 help="""Determines iterations for which models
                                 will be preserved during cleanup.
                                 If mod(iter,preserve_model_interval) == 0
                                 model will be preserved.""")

        self.parser.add_argument("--reporting.email", dest="email",
                                 type=str, default=None,
                                 action=common_lib.NullstrToNoneAction,
                                 help=""" Email-id to report about the progress
                                 of the experiment.  NOTE: It assumes the
                                 machine on which the script is being run can
                                 send emails from command line via. mail
                                 program. The Kaldi mailing list will not
                                 support this feature.  It might require local
                                 expertise to setup. """)
        self.parser.add_argument("--reporting.interval",
                                 dest="reporting_interval",
                                 type=float, default=0.1,
                                 help="""Frequency with which reports have to
                                 be sent, measured in terms of fraction of
                                 iterations.
                                 If 0 and reporting mail has been specified
                                 then only failure notifications are sent""")


import unittest

class SelfTest(unittest.TestCase):

    def test_halve_minibatch_size_str(self):
        self.assertEqual('32', halve_minibatch_size_str('64'))
        self.assertEqual('32,8:16', halve_minibatch_size_str('64,16:32'))
        self.assertEqual('1', halve_minibatch_size_str('1'))
        self.assertEqual('128=32/256=20,40:50', halve_minibatch_size_str('128=64/256=40,80:100'))


    def test_validate_chunk_width(self):
        for s in [ '64', '64,25,128' ]:
            self.assertTrue(validate_chunk_width(s), s)


    def test_validate_minibatch_size_str(self):
        # Good descriptors.
        for s in [ '32', '32,64', '1:32', '1:32,64', '64,1:32', '1:5,10:15',
                   '128=64:128/256=32,64', '1=2/3=4', '1=1/2=2/3=3/4=4' ]:
            self.assertTrue(validate_minibatch_size_str(s), s)
        # Bad descriptors.
        for s in [ None, 42, (43,), '', '1:', ':2', '3,', ',4', '5:6,', ',7:8',
                   '9=', '10=10/', '11=11/11', '12=1:2//13=1:3' '14=/15=15',
                   '16/17=17', '/18=18', '/18', '//19', '/' ]:
            self.assertFalse(validate_minibatch_size_str(s), s)


    def test_get_current_num_jobs(self):
        niters = 12
        self.assertEqual([2, 3, 3, 4, 4, 5, 6, 6, 7, 7, 8, 8],
                         [get_current_num_jobs(i, niters, 2, 1, 9)
                              for i in range(niters)])
        self.assertEqual([2, 3, 3, 3, 3, 6, 6, 6, 6, 6, 9, 9],
                         [get_current_num_jobs(i, niters, 2, 3, 9)
                              for i in range(niters)])


if __name__ == '__main__':
    unittest.main()
