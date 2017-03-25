#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Train an Auxiliary Classifier Generative Adversarial Network (ACGAN) on the
MNIST dataset. See https://arxiv.org/abs/1610.09585 for more detals.

This example is based on the Keras example, which uses the same generator and
discriminator model. It can be found at:

https://github.com/fchollet/keras/blob/master/examples/mnist_acgan.py

Consult https://github.com/lukedeo/keras-acgan for more information about the
model.

In addition to the ACGAN implementation from the Keras examples folder, there
is a lite version of the model, which is faster on CPUs. Either model can be
run both as supervised and unsupervised versions.

To show all command line options:

    ./examples/mnist_gan.py --help

To train the lite version of the model:

    ./examples/mnist_gan.py --lite

Samples from the model can be plotted using Matplotlib:

    ./examples/mnist_gan.py --plot 3

The model can be run in unsupervised mode (pure GAN):

    ./examples/mnist_gan.py --unsupervised
"""

from __future__ import print_function

import argparse

import keras
from keras.datasets import mnist

import gandlf
import numpy as np

# For repeatability.
np.random.seed(1337)

# To make the images work correctly.
keras.backend.set_image_dim_ordering('tf')


def build_generator(latent_size, supervised):
    """Builds the big generator model."""

    cnn = keras.models.Sequential()

    cnn.add(keras.layers.Dense(1024, input_dim=latent_size, activation='relu'))
    cnn.add(keras.layers.Dense(128 * 7 * 7, activation='relu'))
    cnn.add(keras.layers.Reshape((7, 7, 128)))

    cnn.add(keras.layers.UpSampling2D(size=(2, 2)))
    cnn.add(keras.layers.Convolution2D(256, 5, 5, border_mode='same', init='glorot_normal'))
    cnn.add(keras.layers.BatchNormalization(axis=-1)) # normalize per feature map (channels axis)
    cnn.add(keras.layers.Activation('relu'))

    cnn.add(keras.layers.UpSampling2D(size=(2, 2)))
    cnn.add(keras.layers.Convolution2D(128, 5, 5, border_mode='same', init='glorot_normal'))
    cnn.add(keras.layers.BatchNormalization(axis=-1)) # normalize per feature map (channels axis)
    cnn.add(keras.layers.Activation('relu'))

    cnn.add(keras.layers.Convolution2D(1, 2, 2, border_mode='same',
                                       activation='tanh', init='glorot_normal'))

    latent = keras.layers.Input(shape=(latent_size,), name='latent')

    if supervised:
        image_class = keras.layers.Input(shape=(1,), dtype='int32',
                                         name='image_class')

        embed = keras.layers.Embedding(10, latent_size, init='glorot_normal')
        cls = keras.layers.Flatten()(embed(image_class))
        h = keras.layers.merge([latent, cls], mode='mul')
        fake_image = cnn(h)
        return keras.models.Model(input=[latent, image_class],
                                  output=fake_image,
                                  name='generator')
    else:
        fake_image = cnn(latent)
        return keras.models.Model(input=latent,
                                  output=output_fake_image,
                                  name='generator')


def build_discriminator(supervised):
    """Builds the big discriminator model."""

    cnn = keras.models.Sequential()

    cnn.add(keras.layers.Convolution2D(32, 3, 3, border_mode='same',
                                       subsample=(2, 2),
                                       input_shape=(28, 28, 1)))
    cnn.add(keras.layers.LeakyReLU())
    cnn.add(keras.layers.Dropout(0.3))

    cnn.add(keras.layers.Convolution2D(64, 3, 3, border_mode='same',
                                       subsample=(1, 1)))
    cnn.add(keras.layers.LeakyReLU())
    cnn.add(keras.layers.Dropout(0.3))

    cnn.add(keras.layers.Convolution2D(128, 3, 3, border_mode='same',
                                       subsample=(2, 2)))
    cnn.add(keras.layers.LeakyReLU())
    cnn.add(keras.layers.Dropout(0.3))

    cnn.add(keras.layers.Convolution2D(256, 3, 3, border_mode='same',
                                       subsample=(1, 1)))
    cnn.add(keras.layers.LeakyReLU())
    cnn.add(keras.layers.Dropout(0.3))

    cnn.add(keras.layers.Flatten())

    image = keras.layers.Input(shape=(28, 28, 1), name='real_data')

    features = cnn(image)

    fake = keras.layers.Dense(1, activation='sigmoid', name='src')(features)

    if supervised:
        aux = keras.layers.Dense(10, activation='softmax', name='class')(features)
        return keras.models.Model(input=image, output=[fake, aux],
                                  name='discriminator')
    else:
        return keras.models.Model(input=image, output=fake,
                                  name='discriminator')


def build_generator_lite(latent_size, supervised):
    """Builds the much smaller generative model."""

    latent = keras.layers.Input((latent_size,), name='latent')

    if supervised:
        image_class = keras.layers.Input((1,), dtype='int32',
                                         name='image_class')
        embed = keras.layers.Embedding(10, latent_size, init='glorot_normal')
        cls = keras.layers.Flatten()(embed(image_class))
        merged = keras.layers.merge([latent, cls], mode='mul')
        input_vec = keras.layers.BatchNormalization()(merged)
    else:
        input_vec = latent

    hidden = keras.layers.Dense(512)(input_vec)
    hidden = keras.layers.LeakyReLU()(hidden)
    hidden = gandlf.layers.PermanentDropout(0.3)(hidden)

    hidden = keras.layers.Dense(512)(hidden)
    hidden = keras.layers.LeakyReLU()(hidden)
    hidden = gandlf.layers.PermanentDropout(0.3)(hidden)

    output_layer = keras.layers.Dense(28 * 28,
        activation='tanh')(hidden)
    fake_image = keras.layers.Reshape((28, 28, 1))(output_layer)

    if supervised:
        return keras.models.Model(input=[latent, image_class],
                                  output=fake_image)
    else:
        return keras.models.Model(input=latent, output=fake_image)


def build_discriminator_lite(supervised):
    """Builds the much smaller discriminator model."""

    image = keras.layers.Input((28, 28, 1), name='real_data')
    hidden = keras.layers.Flatten()(image)

    # First hidden layer.
    hidden = keras.layers.Dense(512)(hidden)
    hidden = keras.layers.Dropout(0.3)(hidden)
    hidden = keras.layers.LeakyReLU()(hidden)

    # Second hidden layer.
    hidden = keras.layers.Dense(512)(hidden)
    hidden = keras.layers.Dropout(0.3)(hidden)
    hidden = keras.layers.LeakyReLU()(hidden)

    # Output layer.
    fake = keras.layers.Dense(1, activation='sigmoid', name='src')(hidden)

    if supervised:
        aux = keras.layers.Dense(10, activation='softmax', name='class')(hidden)
        return keras.models.Model(input=image, output=[fake, aux])
    else:
        return keras.models.Model(input=image, output=fake)


def load_data(nb_images=None, nb_images_per_label=None, is_pan=False, im_size=56):
    # nb_images : number of images to load
    # nb_images_per_label : number of images per label to load
    # if nb_images is set and nb_images_per_label is None, images are drawn
    # from categories in proportion to their frequency in the dataset.
    # if nb_images_per_label is set and nb_images is None, the categories
    # are re-ballanced
    # is_pan : data conforms to the mnist data shape

    import os, os.path as path
    from glob import glob
    import scipy.misc as misc
    import itertools as it

    #import sklearn.preprocessing
    #files = glob('/like_mnist@2x/*/*.JPEG')
    #labels = sklearn.preprocessing.LabelEncoder().fit_transform(
    #    [path.split(path.split(f)[0])[1] for f in files])
    #images = [misc.imread(f) for f in files] # silently requires Pillow...

    filenames = []
    for root, dirs, files in os.walk('/data/by_yaw'):
        if dirs != []: continue # HACKY use walkdir
        files = [path.join(root, f) for f in files if '.JPEG' in f]
        files = np.random.permutation(files)
        filenames.append(files[:nb_images_per_label])

    labels = list(it.chain.from_iterable([[i]*len(lst) for i,lst in enumerate(filenames)]))
    filenames = list(it.chain.from_iterable(filenames))

    inds = np.random.permutation(len(filenames))[:nb_images]
    filenames, labels = [filenames[i] for i in inds], [labels[i] for i in inds]

    def largest_square_crop(im):
        height, width = im.shape[:2]
        crop_size = min(width, height)
        j = int(round((height - crop_size)/2.))
        i = int(round((width  - crop_size)/2.))
        return im[j:j+crop_size, i:i+crop_size]

    # silently requires Pillow...
    images = [misc.imread(f, mode='P' if is_pan else 'RGB') for f in filenames]
    images = [largest_square_crop(im) for im in images]
    images = [misc.imresize(im, size=(im_size,im_size), interp='bicubic') for im in images]

    # requires numpy > 1.10
    nb_train = int(0.9*len(filenames))
    X_train, y_train = np.stack(images[:nb_train]), labels[:nb_train]
    X_test, y_test = np.stack(images[nb_train:]), labels[nb_train:]

    def make_band_interleaved(pixel_interleaved_image):
        # nimages, nrows, ncols, nchannels
        return np.transpose(pixel_interleaved_image, (0,3,1,2))
    #if not is_pan: X_train, X_test = map(make_band_interleaved, [X_train, X_test])

    X_train = (X_train.astype(np.float32) - 127.5) / 127.5
    if is_pan: X_train = np.expand_dims(X_train, axis=-1)

    X_test = (X_test.astype(np.float32) - 127.5) / 127.5
    if is_pan: X_test = np.expand_dims(X_test, axis=-1)

    y_train = np.expand_dims(y_train, axis=-1)
    y_test = np.expand_dims(y_test, axis=-1)

    return (X_train, y_train), (X_test, y_test)


def get_mnist_data(binarize=False):
    """Puts the MNIST data in the right format."""

    (X_train, y_train), (X_test, y_test) = mnist.load_data()

    if binarize:
        X_test = np.where(X_test >= 10, 1, -1)
        X_train = np.where(X_train >= 10, 1, -1)
    else:
        X_train = (X_train.astype(np.float32) - 127.5) / 127.5
        X_test = (X_test.astype(np.float32) - 127.5) / 127.5

    X_train = np.expand_dims(X_train, axis=-1)
    X_test = np.expand_dims(X_test, axis=-1)

    y_train = np.expand_dims(y_train, axis=-1)
    y_test = np.expand_dims(y_test, axis=-1)

    return (X_train, y_train), (X_test, y_test)


def train_model(args, X_train, y_train, y_train_ohe):
    """This is the core part where the model is trained."""

    adam_optimizer = keras.optimizers.Adam(lr=args.lr, beta_1=args.beta)
    supervised = not args.unsupervised

    if args.lite:
        print('building lite version')
        generator = build_generator_lite(args.nb_latent, supervised)
        discriminator = build_discriminator_lite(supervised)
    else:
        generator = build_generator(args.nb_latent, supervised)
        discriminator = build_discriminator(supervised)

    model = gandlf.Model(generator, discriminator)

    loss_weights = {'src': 1.}
    if supervised:
        loss_weights['class'] = 1.
        loss_weights['class_fake'] = 0.

    loss = {'src': 'binary_crossentropy'}
    if supervised:
        loss['class'] = 'categorical_crossentropy'

    model.compile(optimizer=adam_optimizer, loss=loss,
                  loss_weights=loss_weights)

    outputs = {'src': '1', 'src_fake': '0'}
    if supervised:
        outputs['class'] = y_train_ohe

    inputs = [args.latent_type.lower()]
    inputs += ([] if args.unsupervised else [y_train])
    inputs += [X_train]

    model.fit(inputs, outputs, nb_epoch=args.nb_epoch, batch_size=args.nb_batch)

    return model


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Auxiliary Classifier GAN for MNIST digits.')

    training_params = parser.add_argument_group('training params')
    training_params.add_argument('--nb_epoch', type=int, default=50,
                                 metavar='INT',
                                 help='number of epochs to train')
    training_params.add_argument('--nb_batch', type=int, default=32,
                                 metavar='INT',
                                 help='number of samples per batch')
    training_params.add_argument('--plot', type=int, default=0,
                                 metavar='INT',
                                 help='number of generator samples to plot')
    training_params.add_argument('--binarize', default=False,
                                 action='store_true',
                                 help='if set, make mnist data binary')

    model_params = parser.add_argument_group('model params')
    model_params.add_argument('--nb_latent', type=int, default=10,
                              metavar='INT',
                              help='dimensions in the latent vector')
    model_params.add_argument('--save_path', type=str, metavar='STR',
                              default='/tmp/mnist_gan.keras_model',
                              help='where to save the model after training')
    model_params.add_argument('--lite', default=False, action='store_true',
                              help='if set, trains the lite version instead')
    model_params.add_argument('--unsupervised', default=False,
                              action='store_true',
                              help='if set, model doesn\'t use class labels')
    model_params.add_argument('--latent_type', type=str, default='uniform',
                              metavar='STR',
                              help='"normal" or "uniform"')

    optimizer_params = parser.add_argument_group('optimizer params')
    optimizer_params.add_argument('--lr', type=float, default=0.0002,
                                  metavar='FLOAT',
                                  help='learning rate for Adam optimizer')
    optimizer_params.add_argument('--beta', type=float, default=0.5,
                                  metavar='FLOAT',
                                  help='beta 1 for Adam optimizer')

    args = parser.parse_args()

    if args.plot:
        try:
            import scipy.misc, os
            from PIL import Image
        except ImportError:
            raise ImportError('To plot samples from the generator, you must '
                              'install scipy and Pillow (not found in path).')

    latent_type = args.latent_type.lower()
    if latent_type not in ['normal', 'uniform']:
        raise ValueError('Latent vector must be either "normal" or "uniform", '
                         'got %s.' % args.latent_type)

    # Gets training and testing data.
    #(X_train, y_train), (_, _) = get_mnist_data(args.binarize)
    (X_train, y_train), (_, _) = load_data(is_pan=True, nb_images_per_label=10000, im_size=28)

    # Turns digit labels into one-hot encoded labels.
    y_train_ohe = np.eye(10)[np.squeeze(y_train)]

    model = train_model(args, X_train, y_train, y_train_ohe)

    if args.plot:
        if args.unsupervised:
            samples = model.sample([latent_type], num_samples=args.plot)
            for i, sample in enumerate(samples):
                outfile = 'samples{}.png'.format(i)
                # otherwise saves 16-bit png
                sample = (sample.squeeze() * 127.5 + 127.5).astype(np.ubyte)
                scipy.misc.imsave(outfile, sample)
        else:
            labels = y_train[:args.plot]
            samples = model.sample([latent_type, labels])
            for i, (sample, digit) in enumerate(zip(samples, labels)):
                outfile = 'samples{}_{}.png'.format(i, digit)
                # otherwise saves 16-bit png
                sample = (sample.squeeze()* 127.5 + 127.5).astype(np.ubyte)
                scipy.misc.imsave(outfile, sample)
                print('Digit: %d' % digit)

    model.save(args.save_path)
    print('Saved model:', args.save_path)
