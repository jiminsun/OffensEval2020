import os
from pandas import read_csv
import pickle
import re
import string
from collections import Counter
from functools import reduce, partial

import emoji
from wordsegment import load, segment
from transformers import BertTokenizer, RobertaTokenizer, XLMTokenizer, XLNetTokenizer

resources_dir = '../resources/'

def compose(*funcs):
    """" Compose functions so that they are applied in chain. """
    return reduce(lambda f, g: lambda x: f(g(x)), funcs[::-1])

def textify_emojis(sent):
    tokens = [textify_emojis_token(token) for token in sent.split()]
    return ' '.join(tokens)

def textify_emojis_token(token):
    token = token.strip(':')
    token = re.sub('_', ' ', token)
    return token

def limit_mention(sent, keep_num):
    return _limit_pattern(sent, '@USER', keep_num)

def lower_hashtags(sent):
    return re.sub('#[\w]+', lambda match: match.group().lower(), sent)

def delete_hashtag(sent):
    return re.sub('#[\w]+', '', sent)

def _has_cap(token):
    return token.lower() != token and token.upper() != token

def _all_cap(token):
    return token.lower() != token and token.upper() == token

def add_capital_signs(text):
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

def limit_punctuations(sent, keep_num):
    puncs = ['!', '?', '.']
    for p in puncs:
        sent = _limit_pattern(sent, p, keep_num)
    return sent

def limit_mentions(sent, keep_num):
    return _limit_pattern(sent, '@USER', keep_num)

def replace_emojis(sent):
    """ Replace emoticon with predefined :text:. """
    return emoji.demojize(sent)

def replace_urls(sent):
    return sent.replace('URL', 'http')

def segment_hashtags(sent):
    return re.sub('#[\w]+', lambda match: ' '.join(segment(match.group())), sent)
    #return re.sub('#[\w]+', lambda match: '#' + ' '.join(segment(match.group())), sent) # with '#' in front

def build_preprocess(demojize, mention_limit, punc_limit, lower_hashtag,
                     add_cap_sign, segment_hashtag, textify_emoji):
    funcs = [replace_urls] # default
    if demojize:
        funcs.append(replace_emojis)
    if textify_emoji:
        funcs.append(textify_emojis)
    if mention_limit > 0:
        funcs.append(partial(limit_mentions, keep_num=mention_limit))
    if punc_limit > 0:
        funcs.append(partial(limit_punctuations, keep_num=punc_limit))
    if lower_hashtag:
        funcs.append(lower_hashtags)
    if add_cap_sign:
        funcs.append(add_capital_signs)
    if segment_hashtag:
        load()
        funcs.append(segment_hashtags)
    return compose(*funcs)

# TODO: consider using Config
# TODO: Fix hard code of model names(also in build_model)
def build_tokenizer(model, emoji_min_freq, hashtag_min_freq, add_cap_sign,
                    preprocess):
    if model in {'bert', 'roberta', 'xlm', 'xlnet'}:
        if model == 'bert':
            tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
            tokenizer.add_tokens(['@USER'])
        elif model == 'roberta':
            tokenizer = RobertaTokenizer.from_pretrained('roberta-base')
            tokenizer.add_tokens(['@USER'])
        elif model == 'xlm':
            tokenizer = XLMTokenizer.from_pretrained('xlm-mlm-en-2048')
            tokenizer.add_tokens(['@USER'])
        elif model == 'xlnet':
            tokenizer = XLNetTokenizer.from_pretrained('xlnet-base-cased')
            tokenizer.add_tokens(['@USER'])
        else:
            pass

        if emoji_min_freq > 0:
            new_tokens = get_tokens(load_freq_dict('emoji'), emoji_min_freq)
            tokenizer.add_tokens(new_tokens)
        if hashtag_min_freq > 0:
            new_tokens = get_tokens(load_freq_dict('hashtag'), hashtag_min_freq)
            tokenizer.add_tokens(new_tokens)
        if add_cap_sign:
            tokenizer.add_tokens(['<has_cap>', '<all_cap>'])
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
