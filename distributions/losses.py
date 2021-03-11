import tensorflow as tf
from absl import flags

from distributions import compute_wass_dist, compute_raw_m2_loss, compute_covar_loss, compute_mean_loss

FLAGS = flags.FLAGS


class M1Loss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        return compute_mean_loss(y_true, y_pred)


class M1M2Loss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        mu1, var1 = tf.nn.moments(y_true, axes=[1, 2], keepdims=True)
        mu2, var2 = tf.nn.moments(y_pred, axes=[1, 2], keepdims=True)

        return (mu1 - mu2) ** 2 + (var1 - var2) ** 2


class M1CovarLoss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        mean_loss = compute_mean_loss(y_true, y_pred)
        covar_loss = compute_covar_loss(y_true, y_pred)
        return mean_loss + covar_loss


class GramianLoss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        return compute_raw_m2_loss(y_true, y_pred)


class ThirdMomentLoss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        mu1, var1 = tf.nn.moments(y_true, axes=[1, 2], keepdims=True)
        mu2, var2 = tf.nn.moments(y_pred, axes=[1, 2], keepdims=True)

        z1 = (y_true - mu1) * tf.math.rsqrt(var1 + 1e-3)
        z2 = (y_pred - mu2) * tf.math.rsqrt(var2 + 1e-3)

        skew1 = tf.reduce_mean(z1 ** 3, axis=[1, 2], keepdims=True)
        skew2 = tf.reduce_mean(z2 ** 3, axis=[1, 2], keepdims=True)

        return tf.reduce_mean((mu1 - mu2) ** 2 + (var1 - var2) ** 2 + (skew1 - skew2) ** 2, axis=-1)


class WassLoss(tf.keras.losses.Loss):
    def call(self, y_true, y_pred):
        return compute_wass_dist(y_true, y_pred, p=2)


class CoWassLoss(tf.keras.losses.Loss):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.warmup_steps = tf.Variable(0, trainable=False, dtype=tf.float32)
        self.curr_step = tf.Variable(0, trainable=False, dtype=tf.float32)

    def get_alpha(self):
        if self.warmup_steps <= 0:
            return tf.ones_like(self.curr_step)

        alpha = self.curr_step / self.warmup_steps
        alpha = tf.minimum(alpha, tf.ones_like(alpha))
        return alpha

    def call(self, y_true, y_pred):
        wass_loss = compute_wass_dist(y_true, y_pred, p=2)
        covar_loss = compute_covar_loss(y_true, y_pred)

        alpha = self.get_alpha()
        loss = alpha * wass_loss + covar_loss

        self.curr_step.assign_add(tf.ones_like(self.curr_step))
        return loss



loss_dict = {'m1': M1Loss(), 'm1m2': M1M2Loss(), 'm1covar': M1CovarLoss(), 'gram': GramianLoss(),
             'm3': ThirdMomentLoss(), 'wass': WassLoss(), 'cowass': CoWassLoss(), None: []}
