#I found this code online and adapted it slightly to fit our needs. Whole post is here
#https://ahmedbesbes.com/sentiment-analysis-on-twitter-using-word2vec-and-keras.html

import pandas as pd # provide sql-like data manipulation tools. very handy.
pd.options.mode.chained_assignment = None
import numpy as np # high dimensional vector computing library.
from copy import deepcopy
from string import punctuation
from random import shuffle

import gensim
from gensim.models.word2vec import Word2Vec # the word2vec model gensim class
LabeledSentence = gensim.models.doc2vec.LabeledSentence # we'll talk about this down below

from tqdm import tqdm
tqdm.pandas(desc="progress-bar")

from nltk.tokenize import TweetTokenizer # a tweet tokenizer from nltk.
tokenizer = TweetTokenizer()

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer

#read in data, drop irrelevant columns, name columns appropriately,
#make sure label columns in int form and 0 and 1
def ingest():
    data = pd.read_csv('scripts/trainingandtestdata/big_tweet.csv')
    data.drop(data.columns[1:4], axis=1, inplace=True)
    data.columns = ['sentiment','user','tweets']
    data = data[data.sentiment.isnull() == False]
    data['sentiment'] = data['sentiment'].map(int)
    data['sentiment'] = data['sentiment'].map({4:1, 0:0})
    data = data[data['sentiment'].isnull() == False]
    data.reset_index(inplace=True)
    data.drop('index', axis=1, inplace=True)
    print 'dataset loaded with shape', data.shape
    return data

data = ingest()


#make sure tweets in utf-8, tokenize them (separate them into list),
#and then drop hashtags, @'s, and links'
def tokenize(tweet):
    try:
        tweet = unicode(tweet.decode('utf-8').lower())
        tokens = tokenizer.tokenize(tweet)
        tokens = filter(lambda t: not t.startswith('@'), tokens)
        tokens = filter(lambda t: not t.startswith('#'), tokens)
        tokens = filter(lambda t: not t.startswith('http'), tokens)
        return tokens
    except:
        return 'NC'

#apply tokenize to our tweets and add the results to a new column called tokens
def postprocess(data, n=1000000):
    data = data.head(n)
    data['tokens'] = data['tweets'].progress_map(tokenize)  ## progress_map is a variant of the map function plus a progress bar. Handy to monitor DataFrame creations.
    data = data[data.tokens != 'NC']
    data.reset_index(inplace=True)
    data.drop('index', inplace=True, axis=1)
    return data

data = postprocess(data)

#train test split
x_train, x_test, y_train, y_test = train_test_split(np.array(data.head(1000000).tokens),
                                                    np.array(data.head(1000000).sentiment), test_size=0.2)

#for all the tweets, iterate through them, and make a list of tweets with their label
#(train or test), and return a list with this labeled tweets to each respective grouping
def labelizeTweets(tweets, label_type):
    labelized = []
    for i,v in tqdm(enumerate(tweets)):
        label = '%s_%s'%(label_type,i)
        labelized.append(LabeledSentence(v, [label]))
    return labelized


#call the function above
x_train = labelizeTweets(x_train, 'TRAIN')
x_test = labelizeTweets(x_test, 'TEST')

#instantiate word2vec model and build it's vocab using out train data
#then train the ,pde;
x_train[0]
tweet_w2v = Word2Vec(size=200, min_count=10)
tweet_w2v.build_vocab([x.words for x in tqdm(x_train)])
tweet_w2v.train([x.words for x in tqdm(x_train)],total_examples=tweet_w2v.corpus_count, epochs=tweet_w2v.iter)
tweet_w2v['good']

# importing bokeh library for interactive dataviz (I don't use it, but the guy had it
#so I figured I'd leave it in)
import bokeh.plotting as bp
from bokeh.models import HoverTool, BoxSelectTool
from bokeh.plotting import figure, show, output_notebook

# defining the chart
output_notebook()
plot_tfidf = bp.figure(plot_width=700, plot_height=600, title="A map of 10000 word vectors",
    tools="pan,wheel_zoom,box_zoom,reset,hover,previewsave",
    x_axis_type=None, y_axis_type=None, min_border=1)

# getting a list of word vectors. limit to 10000. each is of 200 dimensions
word_vectors = [tweet_w2v[w] for w in tweet_w2v.wv.vocab.keys()[:5000]]

# dimensionality reduction. converts a lot of dimensions into 2
from sklearn.manifold import TSNE
tsne_model = TSNE(n_components=2, verbose=1, random_state=0)
tsne_w2v = tsne_model.fit_transform(word_vectors)

# putting everything in a dataframe
tsne_df = pd.DataFrame(tsne_w2v, columns=['x', 'y'])
tsne_df['words'] = tweet_w2v.wv.vocab.keys()[:5000]

# plotting. the corresponding word appears when you hover on the data point.
plot_tfidf.scatter(x='x', y='y', source=tsne_df)
hover = plot_tfidf.select(dict(type=HoverTool))
hover.tooltips={"word": "@words"}
show(plot_tfidf)


#tf-idf is a way of determining a word's importance in a group of documents. If it
#appears a lot of times in just 1-2 documents, its probably really important, but
#if it appears a lot in all documents, it's probably meaningless
print 'building tf-idf matrix ...'
vectorizer = TfidfVectorizer(analyzer=lambda x: x, min_df=10)
matrix = vectorizer.fit_transform([x.words for x in x_train])
tfidf = dict(zip(vectorizer.get_feature_names(), vectorizer.idf_))
print 'vocab size :', len(tfidf)

#for each word, we create a vector representation of each word in shape 1,200
def buildWordVector(tokens, size):
    vec = np.zeros(size).reshape((1, size))
    count = 0.
    for word in tokens:
        try:
            vec += tweet_w2v[word].reshape((1, size)) * tfidf[word]
            count += 1.
        except KeyError: # handling the case where the token is not
                         # in the corpus. useful for testing.
            continue
    if count != 0:
        vec /= count
    return vec

#using function above, create numpy matrix of word vectors, and then scale the
#values to a mean and unit variance
from sklearn.preprocessing import scale
train_vecs_w2v = np.concatenate([buildWordVector(z, 200) for z in tqdm(map(lambda x: x.words, x_train))])
train_vecs_w2v = scale(train_vecs_w2v)

test_vecs_w2v = np.concatenate([buildWordVector(z, 200) for z in tqdm(map(lambda x: x.words, x_test))])
test_vecs_w2v = scale(test_vecs_w2v)

#here we instantiate a neural net that will take our words and first learn the vector->sentiment
#relationship, and then predict on it's own. THis model could then be used to
#find the sentiment of other tweets. Accuracy typically around 80-90%.
from keras.models import Sequential
from keras.layers import Activation, Dense
model = Sequential()
model.add(Dense(32, activation='relu', input_dim=200))
model.add(Dense(1, activation='sigmoid'))
model.compile(optimizer='rmsprop',
              loss='binary_crossentropy',
              metrics=['accuracy'])

model.fit(train_vecs_w2v, y_train, epochs=5, batch_size=32, verbose=2)

score = model.evaluate(test_vecs_w2v, y_test, batch_size=128, verbose=2)
print score[1]
