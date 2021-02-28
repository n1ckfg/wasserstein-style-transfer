import os

import tensorflow as tf
from absl import app
from absl import flags
from absl import logging

import discriminators as disc
import style_content as sc
import utils
import datetime

FLAGS = flags.FLAGS
flags.DEFINE_float('lr', 1e-3, 'learning rate')
flags.DEFINE_float('beta1', 0.5, 'learning rate')
flags.DEFINE_float('beta2', 0.75, 'learning rate')
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
    losses = {'style': [sc.make_discriminator() for _ in sc_model.feat_model.output['style']]}
    if FLAGS.content_image is not None:
        losses['content'] = [tf.keras.losses.MeanSquaredError() for _ in sc_model.feat_model.output['content']]
    sc_model.compile(tf.keras.optimizers.Adam(FLAGS.lr, FLAGS.beta1, FLAGS.beta2), loss=losses)
    tf.keras.utils.plot_model(sc_model.feat_model, './out/feat_model.jpg')

    # Run the style model
    start_time = datetime.datetime.now()
    feats_dict = sc_model((style_image, content_image))
    sc_model.fit((style_image, content_image), feats_dict, epochs=FLAGS.train_steps, batch_size=1,
                 verbose=FLAGS.verbose, callbacks=tf.keras.callbacks.CSVLogger('./out/logs.csv'))
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    logging.info(f'training took {duration}')

    # Get generated image
    gen_image = sc_model.get_gen_image()

    # Save the generated image to disk
    tf.keras.preprocessing.image.save_img(os.path.join('./out', 'style.jpg'), tf.squeeze(style_image, 0))
    tf.keras.preprocessing.image.save_img(os.path.join('./out', 'content.jpg'), tf.squeeze(content_image, 0))
    tf.keras.preprocessing.image.save_img(os.path.join('./out', 'gen.jpg'), tf.squeeze(gen_image, 0))
    logging.info(f'images saved to ./out')


if __name__ == '__main__':
    app.run(main)
