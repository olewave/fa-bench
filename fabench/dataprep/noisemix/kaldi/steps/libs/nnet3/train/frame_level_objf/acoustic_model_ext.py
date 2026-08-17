
#           2020    Wei Chu

# Copyright 2016    Vijayaditya Peddinti.
#           2016    Vimal Manohar
# Apache 2.0.

""" Extend the generate egs to switch from 2 ivector dirs/Extend the evenly generate egs from 2 classes
""" 

import logging

import libs.common as common_lib

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def generate_switch_ivector_egs(data, l1_data, l2_data, l1_alidir, l2_alidir, egs_dir,
                 left_context, right_context,
                 run_opts, stage=0,
                 left_context_initial=-1, right_context_final=-1,
                 l1_online_ivector_dir=None,
                 l2_online_ivector_dir=None,
                 samples_per_iter=20000, frames_per_eg_str="20", srand=0,
                 egs_opts=None, cmvn_opts=None):

    """ Wrapper for calling steps/nnet3/get_egs.sh

    Generates targets from alignment directory 'alidir', which contains
    the model final.mdl and alignments.
    """

    common_lib.execute_command(
        """steps/nnet3/get_switch_ivector_egs.sh {egs_opts} \
                --cmd "{command}" \
                --cmvn-opts "{cmvn_opts}" \
                --l1-online-ivector-dir "{l1_ivector_dir}" \
                --l2-online-ivector-dir "{l2_ivector_dir}" \
                --left-context {left_context} \
                --right-context {right_context} \
                --left-context-initial {left_context_initial} \
                --right-context-final {right_context_final} \
                --stage {stage} \
                --samples-per-iter {samples_per_iter} \
                --frames-per-eg {frames_per_eg_str} \
                --srand {srand} \
                {data} {l1_data} {l2_data} {l1_alidir} {l2_alidir} {egs_dir}
        """.format(command=run_opts.egs_command,
                    cmvn_opts=cmvn_opts if cmvn_opts is not None else '',
                    l1_ivector_dir=(l1_online_ivector_dir
                                if l1_online_ivector_dir is not None
                                else ''),
                    l2_ivector_dir=(l2_online_ivector_dir
                                if l2_online_ivector_dir is not None
                                else ''),
                   left_context=left_context,
                   right_context=right_context,
                   left_context_initial=left_context_initial,
                   right_context_final=right_context_final,
                   stage=stage, samples_per_iter=samples_per_iter,
                   frames_per_eg_str=frames_per_eg_str, srand=srand, data=data, l1_data=l1_data, l2_data=l2_data,
                   l1_alidir=l1_alidir, l2_alidir=l2_alidir, egs_dir=egs_dir,
                   egs_opts=egs_opts if egs_opts is not None else ''))

def generate_switch_ivector_egs_3ways(data, l1_data, l2_data, l3_data, l1_alidir, l2_alidir, l3_alidir, egs_dir,
                 left_context, right_context,
                 run_opts, stage=0,
                 left_context_initial=-1, right_context_final=-1,
                 l1_online_ivector_dir=None,
                 l2_online_ivector_dir=None,
                 l3_online_ivector_dir=None,
                 samples_per_iter=20000, frames_per_eg_str="20", srand=0,
                 egs_opts=None, cmvn_opts=None):

    """ Wrapper for calling steps/nnet3/get_switch_ivector_egs_3ways.sh

    Generates targets from alignment directory 'alidir', which contains
    the model final.mdl and alignments.
    """

    common_lib.execute_command(
        """steps/nnet3/get_switch_ivector_egs_3ways.sh {egs_opts} \
                --cmd "{command}" \
                --cmvn-opts "{cmvn_opts}" \
                --l1-online-ivector-dir "{l1_ivector_dir}" \
                --l2-online-ivector-dir "{l2_ivector_dir}" \
                --l3-online-ivector-dir "{l3_ivector_dir}" \
                --left-context {left_context} \
                --right-context {right_context} \
                --left-context-initial {left_context_initial} \
                --right-context-final {right_context_final} \
                --stage {stage} \
                --samples-per-iter {samples_per_iter} \
                --frames-per-eg {frames_per_eg_str} \
                --srand {srand} \
                {data} {l1_data} {l2_data} {l3_data} {l1_alidir} {l2_alidir} {l3_alidir} {egs_dir}
        """.format(command=run_opts.egs_command,
                    cmvn_opts=cmvn_opts if cmvn_opts is not None else '',
                    l1_ivector_dir=(l1_online_ivector_dir
                                if l1_online_ivector_dir is not None
                                else ''),
                    l2_ivector_dir=(l2_online_ivector_dir
                                if l2_online_ivector_dir is not None
                                else ''),
                    l3_ivector_dir=(l3_online_ivector_dir
                                if l3_online_ivector_dir is not None
                                else ''),
                   left_context=left_context,
                   right_context=right_context,
                   left_context_initial=left_context_initial,
                   right_context_final=right_context_final,
                   stage=stage, samples_per_iter=samples_per_iter,
                   frames_per_eg_str=frames_per_eg_str, srand=srand, data=data, l1_data=l1_data, l2_data=l2_data,
                   l3_data=l3_data, l1_alidir=l1_alidir, l2_alidir=l2_alidir, l3_alidir=l3_alidir, egs_dir=egs_dir,
                   egs_opts=egs_opts if egs_opts is not None else ''))

def generate_even_egs(data, l1_data, l2_data, l1_alidir, l2_alidir, egs_dir,
                 left_context, right_context,
                 run_opts, stage=0,
                 left_context_initial=-1, right_context_final=-1,
                 l1_online_ivector_dir=None,
                 l2_online_ivector_dir=None,
                 samples_per_iter=20000, frames_per_eg_str="20", srand=0,
                 egs_opts=None, cmvn_opts=None):

    """ Wrapper for calling steps/nnet3/get_egs.sh

    Generates targets from alignment directory 'alidir', which contains
    the model final.mdl and alignments.
    """

    common_lib.execute_command(
        """steps/nnet3/get_even_egs.sh {egs_opts} \
                --cmd "{command}" \
                --cmvn-opts "{cmvn_opts}" \
                --l1-online-ivector-dir "{l1_ivector_dir}" \
                --l2-online-ivector-dir "{l2_ivector_dir}" \
                --left-context {left_context} \
                --right-context {right_context} \
                --left-context-initial {left_context_initial} \
                --right-context-final {right_context_final} \
                --stage {stage} \
                --samples-per-iter {samples_per_iter} \
                --frames-per-eg {frames_per_eg_str} \
                --srand {srand} \
                {data} {l1_data} {l2_data} {l1_alidir} {l2_alidir} {egs_dir}
        """.format(command=run_opts.egs_command,
                    cmvn_opts=cmvn_opts if cmvn_opts is not None else '',
                    l1_ivector_dir=(l1_online_ivector_dir
                                if l1_online_ivector_dir is not None
                                else ''),
                    l2_ivector_dir=(l2_online_ivector_dir
                                if l2_online_ivector_dir is not None
                                else ''),
                   left_context=left_context,
                   right_context=right_context,
                   left_context_initial=left_context_initial,
                   right_context_final=right_context_final,
                   stage=stage, samples_per_iter=samples_per_iter,
                   frames_per_eg_str=frames_per_eg_str, srand=srand, data=data, l1_data=l1_data, l2_data=l2_data,
                   l1_alidir=l1_alidir, l2_alidir=l2_alidir, egs_dir=egs_dir,
                   egs_opts=egs_opts if egs_opts is not None else ''))