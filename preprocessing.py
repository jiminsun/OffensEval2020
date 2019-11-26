import os
from pandas import read_csv
import pickle
import re
import string
from collections import Counter
from functools import reduce, partial

import emoji
from transformers import BertTokenizer

resources_dir = '../resources/'

def compose(*funcs):
    """" Compose functions so that they are applied in chain. """
    return reduce(lambda f, g: lambda x: f(g(x)), funcs[::-1])

def demojize(sent):
    """ Replace emoticon with predefined :text:. """
    return emoji.demojize(sent)

# TODO: need a space after the last `@USER`
# def del_mention(sent, keep_num):
#     """Consecutive `@USER` up to kee_num times"""
#     return re.sub('((@USER)[\s]*){' + str(keep_num+1) + ',}', lambda match: '@USER '*keep_num, sent)

def limit_mention(sent, keep_num):
    return _limit_pattern(sent, '@USER', keep_num)

def lower_hashtag(sent):
    return re.sub('#[\w]+', lambda match: match.group().lower(), sent)

def _has_cap(token):
    return token.lower() != token and token.upper() != token

def _all_cap(token):
    return token.lower() != token and token.upper() == token

def add_capital_sign(text):
    exceptions = ['@USER', 'URL']
    tokens = text.split()
    tokens = ['<has_cap> ' + t if _has_cap(t) and t not in exceptions else t for t in tokens]
    tokens = ['<all_cap> ' + t if _all_cap(t) and t not in exceptions else t for t in tokens]
    return ' '.join(tokens)

def _limit_pattern(sent, pattern, keep_num):
    if pattern in string.punctuation:
        re_pattern = re.escape(pattern)
    else:
        re_pattern = f'(({pattern})[\s]*)'
        pattern = pattern + ' '
    pattern_regex = re_pattern + '{' + str(keep_num+1) + ',}'
    return re.sub(pattern_regex, lambda match: pattern * keep_num, sent)

def limit_punctuation(sent, keep_num):
    puncs = ['!', '?', '.']
    for p in puncs:
        sent = _limit_pattern(sent, p, keep_num)
    return sent

# TODO
def numbers():
    pass

# TODO:
def stopwords():
    pass

def replace_urls(sent):
    return sent.replace('URL', 'http')

def build_preprocess(keep_emoji, keep_mention_num, keep_hashtag, add_cap_sign, limit_punc):
    funcs = [replace_urls] # default
    if not keep_emoji:
        funcs.append(demojize)
    if keep_mention_num > 0:
        funcs.append(partial(limit_mention, keep_num=keep_mention_num))
    if not keep_hashtag:
        funcs.append(lower_hashtag)
    if add_cap_sign:
        funcs.append(add_capital_sign)
    if limit_punc:
        funcs.append(limit_punctuation)
    return compose(*funcs)

def build_tokenizer(model, emoji_min_freq=None, hashtag_min_freq=None,
                    preprocess=None):
    if 'bert' in model:
        # TODO: Fix hard code here
        tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        tokenizer.add_tokens(['@USER'])
        if emoji_min_freq is not None:
            new_tokens = get_tokens(load_freq_dict('emoji'), emoji_min_freq)
            tokenizer.add_tokens(new_tokens)
        if hashtag_min_freq is not None:
            new_tokens = get_tokens(load_freq_dict('hashtag'), hashtag_min_freq)
            tokenizer.add_tokens(new_tokens)
        if preprocess is not None:
            tokenizer.tokenize = compose(preprocess, tokenizer.tokenize)

    else:
        # TODO: when not using bert
        pass
    return tokenizer

def build_freq_dict(train_corpus, which):
    freq_dict = count(train_corpus, which)
    with open(resources_dir + f'{which}.count', 'wb') as f:
        pickle.dump(freq_dict, f)
    print(f"Built frequency dict {which}.count")

def count(text, which):
    regex = emoji.get_emoji_regexp() if which == 'emoji' else re.compile('#[\w]+')
    tokens = regex.findall(text.lower())
    tokens = list(map(emoji.demojize, tokens)) if which == 'emoji' else tokens
    counts = Counter(tokens)
    return counts

def load_freq_dict(which):
    fpath = os.path.join(resources_dir, f"{which}.count")
    if not os.path.exists(fpath):
        train_corpus = load_corpus()
        build_freq_dict(train_corpus, which)
    with open(fpath, 'rb') as f:
        freq_dict = pickle.load(f)
    return freq_dict

def load_corpus(train_path='../data/olid-training-v1.0.tsv'):
    df = read_csv(train_path, sep='\t', usecols=['tweet'])
    return ' '.join(df['tweet'])

def get_tokens(counter, min_freq):
    return [token for token, freq in counter.items() if freq >= min_freq]

if __name__ == "__main__":
    tokenizer = build_tokenizer('bert', 3, 3)
