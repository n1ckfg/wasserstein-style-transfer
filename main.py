import datetime
import os

import matplotlib.pyplot as plt
import pandas as pd
import tensorflow as tf
import tensorflow_addons as tfa
from absl import app
from absl import flags
from absl import logging

import dist_losses
import dist_metrics
import style_content as sc
import utils

FLAGS = flags.FLAGS

flags.DEFINE_float('lr', 1e-3, 'learning rate')
flags.DEFINE_float('beta1', 0.9, 'beta1')
flags.DEFINE_float('beta2', 0.99, 'beta2')
flags.DEFINE_float('epsilon', 1e-5, 'epsilon')

flags.DEFINE_integer('train_steps', 100, 'train steps')


def main(argv):
    del argv  # Unused.

    strategy = utils.setup()

    # Load style/content image
    logging.info('loading images')
    style_image, content_image = utils.load_sc_images()

    # Create the style-content model
    logging.info('making style-content model')
    with strategy.scope():
        sc_model = sc.SCModel(style_image.shape[1:])

        losses = {'style': [dist_losses.loss_dict[FLAGS.disc] for _ in sc_model.feat_model.output['style']]}
        metrics = {'style': [[dist_metrics.MeanLoss(), dist_metrics.VarLoss(), dist_metrics.SkewLoss()] for _ in
                             sc_model.feat_model.output['style']],
                   'content': [[] for _ in sc_model.feat_model.output['content']]}
        if FLAGS.content_image is not None:
            losses['content'] = [tf.keras.losses.MeanSquaredError() for _ in sc_model.feat_model.output['content']]

        sc_model.compile(tf.keras.optimizers.Adam(FLAGS.lr, FLAGS.beta1, FLAGS.beta2, FLAGS.epsilon), loss=losses, metrics=metrics)
    tf.keras.utils.plot_model(sc_model.feat_model, './out/feat_model.jpg')

    # Configure batch norm layers to normalize features of the style and content images
    sc_model.feat_model((style_image, content_image), training=True)
    sc_model.feat_model.trainable = False

    # Log distribution statistics of the style image
    feats_dict = sc_model.feat_model((style_image, content_image), training=False)
    moments = []
    for style_feats in feats_dict['style']:
        m1 = tf.reduce_mean(style_feats, axis=[1, 2]).numpy()
        m2 = tf.math.reduce_variance(style_feats, axis=[1, 2]).numpy()
        m3 = utils.compute_skewness(style_feats, axes=[1, 2]).numpy()
        moments.append([m1, m2, m3])
    logging.info('=' * 100)
    logging.info('average style moments')
    logging.info(f"\tmean: {[m[0].mean() for m in moments]}")
    logging.info(f"\tvar: {[m[1].mean() for m in moments]}")
    logging.info(f"\tskew: {[m[2].mean() for m in moments]}")
    logging.info('=' * 100)

    # Run the style model
    start_time = datetime.datetime.now()
    sc_model.fit((style_image, content_image), feats_dict, epochs=FLAGS.train_steps, batch_size=1,
                 verbose=FLAGS.verbose, callbacks=tf.keras.callbacks.CSVLogger('./out/logs.csv'))
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    logging.info(f'training took {duration}')

    metrics = sc_model.evaluate((style_image, content_image), feats_dict, batch_size=1, return_dict=True)
    logging.info(metrics)

    # Get generated image
    gen_image = sc_model.get_gen_image()

    # Save the generated image to disk
    tf.keras.preprocessing.image.save_img(os.path.join('./out', 'style.jpg'), tf.squeeze(style_image, 0))
    tf.keras.preprocessing.image.save_img(os.path.join('./out', 'content.jpg'), tf.squeeze(content_image, 0))
    tf.keras.preprocessing.image.save_img(os.path.join('./out', 'gen.jpg'), tf.squeeze(gen_image, 0))
    logging.info(f'images saved to ./out')

    # Plot loss
    logs_df = pd.read_csv('out/logs.csv')
    logs_df.set_index('epoch')
    f, axes = plt.subplots(1, 4)
    f.set_size_inches(16, 3)
    logs_df.plot(y='loss', logy=True, ax=axes[0])
    logs_df.filter(like='mean').plot(logy=True, ax=axes[1])
    logs_df.filter(like='var').plot(logy=True, ax=axes[2])
    logs_df.filter(like='skew').plot(logy=True, ax=axes[3])
    f.tight_layout()
    f.savefig('out/metrics.jpg')


if __name__ == '__main__':
    app.run(main)
