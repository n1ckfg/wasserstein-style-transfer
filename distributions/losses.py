import tensorflow as tf
from absl import flags

from distributions import compute_wass_dist, compute_raw_m2_loss, compute_covar_loss, compute_mean_loss, \
    compute_var_loss

FLAGS = flags.FLAGS


class NoOpLoss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        return tf.zeros(tf.shape(y_true)[0], dtype=y_true.dtype)


class M1Loss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        return compute_mean_loss(y_true, y_pred, p=2)


class M1M2Loss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        mean_loss = compute_mean_loss(y_true, y_pred, p=2)
        var_loss = compute_var_loss(y_true, y_pred, p=2)
        return mean_loss + var_loss


class M1CovarLoss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        mean_loss = compute_mean_loss(y_true, y_pred, p=2)
        covar_loss = compute_covar_loss(y_true, y_pred, p=2)
        return mean_loss + covar_loss


class GramianLoss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        return compute_raw_m2_loss(y_true, y_pred, p=2)


class WassLoss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        return compute_wass_dist(y_true, y_pred, p=2)


class CoWassLoss(tf.keras.losses.Loss):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.warmup_steps = tf.Variable(0, trainable=False, dtype=tf.float32)
        self.curr_step = tf.Variable(0, trainable=False, dtype=tf.float32)

    def get_alpha(self):
        alpha = tf.ones_like(self.curr_step / self.warmup_steps)
        alpha = tf.cond(self.warmup_steps <= tf.zeros_like(self.warmup_steps),
                        lambda: tf.ones_like(self.curr_step),
                        lambda: tf.minimum(alpha, self.curr_step / self.warmup_steps))
        return alpha

    def call(self, y_true, y_pred):
        wass_loss = compute_wass_dist(y_true, y_pred, p=2)
        covar_loss = compute_covar_loss(y_true, y_pred, p=2)

        alpha = self.get_alpha()
        loss = alpha * wass_loss + covar_loss

        self.curr_step.assign_add(tf.ones_like(self.curr_step))
        return loss


loss_dict = {'m1': M1Loss, 'm1m2': M1M2Loss, 'm1covar': M1CovarLoss, 'gram': GramianLoss, 'wass': WassLoss,
             'cowass': CoWassLoss, None: NoOpLoss}
