import re
import logging

#CIGAR STRING OPERATORS and BAM CODES
#    M   BAM_CMATCH  0
#    I   BAM_CINS    1
#    D   BAM_CDEL    2
#    N   BAM_CREF_SKIP   3
#    S   BAM_CSOFT_CLIP  4
#    H   BAM_CHARD_CLIP  5
#    P   BAM_CPAD    6
#    =   BAM_CEQUAL  7
#    X   BAM_CDIFF   8
#    B   BAM_CBACK   9
_cigar_score = {
    0: lambda x: x, 
    1: lambda x: -6 - x, 
    2: lambda x: -6 - x,
    3: lambda x: 0, 
    4: lambda x: 0, 
    5: lambda x: 0, 
    #4: lambda x: x * -0.5, 
    #5: lambda x: x * -0.5, 
    6: lambda x: 0, 
    7: lambda x: x,
    8: lambda x: x * -1,
    9: lambda x: 0,
}
#cigar parsing strategy borrowed from pysam libcalignedsegment.pyx
CIGAR_REGEX = re.compile("(\d+)([MIDNSHP=XB])")  
CIGAR2CODE = dict([y, x] for x, y in enumerate("MIDNSHP=XB"))

MD_REGEX = re.compile(r"([A-Za-z]+|\^[A-Za-z])")


class CigarScorer(object):
    ''' 
        Object for scoring a cigar string penalising clipping and 
        indels.
    '''

    def __init__(self, logging_level=logging.INFO):
        ''' 
            Args:
                logging_level: Set logging level. Default = logging.INFO

        '''
        self.logger = logging.getLogger(__name__)
        self.cig_warned = set()
        if not self.logger.handlers:
             self.logger.setLevel(logging_level) 
             formatter = logging.Formatter(
                        '[%(asctime)s] %(name)s - %(levelname)s - %(message)s')                                                                                                          
             ch = logging.StreamHandler() 
             ch.setLevel(self.logger.level)
             ch.setFormatter(formatter)
             self.logger.addHandler(ch)

    def score_cigarstring(self, cigar):
        ''' Score a cigar string as found in field 6 of a SAM file '''
        cigartups = self.cigarstring_to_tuples(cigar)
        return self.score_cigartuples(cigartups)

    def cigarstring_to_tuples(self, cigar):
        ''' 
            Uses an approach borrowed from pysam to convert a cigar 
            string to a list of tuples.
        '''
        #adapted from pysam
        parts = CIGAR_REGEX.findall(cigar)                              
        return [(CIGAR2CODE[y], int(x)) for x,y in parts]

    def score_cigartuples(self, ctups):
        ''' Score cigar tuples as generated by pysam AlignedSegment'''
        score = 0
        for c in ctups:
            try:
                score += _cigar_score[c[0]](c[1])
            except KeyError:
                if c[0] not in self.cig_warned:
                    self.logger.warn("Unrecognized operator code found " + 
                                     "in CIGAR STRING: '{}'".format(c[0]))
                    self.cig_warned.add(c[0])
        return score
    
    def get_clipped_offset(self, ctups):
        '''
            For a list of cigar tuples (as generated by pysam 
            AlignedSegment or self.cigarstring_to_tuples()) return a 
            tuple containing the start offset and end offset according
            to softclipped bases at the start and end of the read.
        '''
        if len(ctups) < 1:
            return (0, 0)
        s_off, e_off = (0, 0)
        if ctups[0][0] == 4:
            s_off = ctups[0][1]
        if ctups[-1][0] == 4:
            e_off = ctups[-1][1]
        return (s_off, e_off)

    def get_aligned_length(self, ctups):
        ''' 
            For a list of cigar tuples (as generated by pysam 
            AlignedSegment or self.cigarstring_to_tuples()) return the
            number of reference nucleotides covered by the read.
        '''
        i = 0
        for c in ctups:
            if c[0] == 0 or 2 <= c[0] <= 3 or 7 <= c[0] <= 8:
                i += c[1]
        return i

    def md_mismatches(self, md_tag):
        '''
            Using the MD tag from an alignment, returns the number of 
            single nucleotide mismatches.
        '''
        p = 0
        for x in MD_REGEX.findall(md_tag):
            if x[0].isalpha():
                p += len(x)
        return p

