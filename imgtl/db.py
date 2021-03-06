#!/usr/bin/env python
# -*- coding: utf-8 -*-

import simplejson

from datetime import datetime
from urllib import urlencode

from flask.ext.sqlalchemy import SQLAlchemy

import sqlalchemy.types as types
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.sql import functions as sqlfuncs
from sqlalchemy.orm import validates

from .const import BASE_URL, TYPE_FILE, TYPE_IMAGE, TYPE_TEXT, USER_DEFAULT_ICON, ADMIN_IDS
from .lib import md5, get_ext


db = SQLAlchemy()
log_db = SQLAlchemy(session_options={
    'autocommit': True,
})

class JsonEncodedDict(types.TypeDecorator):
    impl = types.String

    def process_bind_param(self, value, dialect):
        return simplejson.dumps(value)

    def process_result_value(self, value, dialect):
        return simplejson.loads(value)

    def copy(self):
        return JsonEncodedDict(self.impl.length)


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column('user_id', db.Integer, primary_key=True)
    email = db.Column('user_email', db.String(120), unique=True, index=True, nullable=False)
    name = db.Column('user_name', db.String(16), unique=True, index=True, nullable=False)
    password = db.Column('user_password', db.String(60), nullable=True)
    token = db.Column('user_token', db.String(32), unique=True, index=True, nullable=True)
    oauth_uid = db.Column('user_oauth_uid', db.Integer, unique=True, index=True, nullable=True)

    @property
    def profile_image_url(self):
        url = 'https://secure.gravatar.com/avatar/%s?%s' % (md5(self.email.lower()), urlencode({'d': USER_DEFAULT_ICON}))
        return url

    @property
    def uploads(self):
        return self.all_uploads.filter_by(deleted=False)

    @property
    def is_admin(self):
        return self.id in ADMIN_IDS

    def get_id(self):
        return unicode(self.id)

    def is_active(self):
        return True

    def is_authenticated(self):
        return True

    def is_anonymous(self):
        return False

    def __repr__(self):
        return '<User %r>' % self.email


class Upload(db.Model):
    __tablename__ = 'upload'
    id = db.Column('upload_id', db.Integer, primary_key=True, index=True)
    url = db.Column('upload_url', db.String(8), unique=True, index=True, nullable=False)
    object_id = db.Column('upload_obj_id', db.Integer, db.ForeignKey('object.object_id'), nullable=False)
    object = db.relationship('Object', backref=db.backref('uploads', lazy='select'))
    user_id = db.Column('upload_user_id', db.Integer, db.ForeignKey('user.user_id'), nullable=True)
    user = db.relationship('User', backref=db.backref('all_uploads', lazy='dynamic'))
    time = db.Column('upload_time', db.DateTime, nullable=False, default=sqlfuncs.now())
    view_count = db.Column('upload_view_count', db.Integer, nullable=False, default=0)
    title = db.Column('upload_title', db.String(120), nullable=False)
    desc = db.Column('upload_desc', db.String(320), nullable=True)
    nsfw = db.Column('upload_nsfw', db.Boolean, nullable=False, default=False)
    anonymous = db.Column('upload_anonymous', db.Boolean, nullable=False, default=False)
    private = db.Column('upload_private', db.Boolean, nullable=False, default=False)
    deleted = db.Column('upload_deleted', db.Boolean, nullable=False, default=False)
    expire_time = db.Column('upload_expire_time', db.DateTime, nullable=True)
    expire_behavior = db.Column('upload_expire_behavior', db.Integer, nullable=True)

    @property
    def page_url(self):
        return BASE_URL % (self.url)

    @property
    def direct_url(self):
        return BASE_URL % ('%s.%s' % (self.url, self.object.ext))

    @property
    def thumbnail_url(self):
        return BASE_URL % ('thumb/%s' % self.url)

    @property
    def is_expired(self):
        if self.expire_time:
            return (datetime.now() - self.expire_time).total_seconds() >= 0
        return False

    def __repr__(self):
        return '<Upload %r>' % self.id


class Object(db.Model):
    __tablename__ = 'object'
    id = db.Column('object_id', db.Integer, primary_key=True, index=True)
    code = db.Column('object_code', db.String(40), unique=True, nullable=False)
    discriminator = db.Column('type', db.Integer)
    __mapper_args__ = {'polymorphic_on': discriminator}


class Image(Object):
    __tablename__ = 'image'
    __mapper_args__ = {'polymorphic_identity': TYPE_IMAGE}
    id = db.Column('image_id', db.Integer, db.ForeignKey('object.object_id'), primary_key=True, index=True)
    server = db.Column('image_srv', db.Integer, nullable=False)
    prop = db.Column('image_prop', MutableDict.as_mutable(JsonEncodedDict), nullable=False)

    @property
    def ext(self):
        return get_ext(self.code)

    def __repr__(self):
        return '<Image %r>' % self.id


class File(Object):
    __tablename__ = 'file'
    __mapper_args__ = {'polymorphic_identity': TYPE_FILE}
    id = db.Column('file_id', db.Integer, db.ForeignKey('object.object_id'), primary_key=True, index=True)
    type = db.Column('file_type', db.Integer, nullable=False)

    def __repr__(self):
        return '<File %r>' % self.id


class Text(Object):
    __tablename__ = 'text'
    __mapper_args__ = {'polymorphic_identity': TYPE_TEXT}
    id = db.Column('text_id', db.Integer, db.ForeignKey('object.object_id'), primary_key=True, index=True)
    cont = db.Column('text_cont', db.Text, nullable=False)

    @validates('cont')
    def generate_code(self, key, cont):
        self.code = md5(cont)
        return cont

    def __repr__(self):
        return '<Text %r>' % self.id


class Log(db.Model):
    __tablename__ = 'log'
    id = db.Column('log_id', db.Integer, primary_key=True, index=True)
    target = db.Column('log_target', db.String(16), nullable=False)
    action = db.Column('log_action', db.String(16), nullable=False)
    action_id = db.Column('log_action_id', db.Integer, nullable=False)
    ip = db.Column('log_by_ip', db.String(16), nullable=True)
    user_id = db.Column('log_by_user_id', db.Integer, db.ForeignKey('user.user_id'), nullable=True)
    user = db.relationship('User', backref=db.backref('logs', lazy='select'))
    time = db.Column('log_time', db.DateTime, nullable=False, default=sqlfuncs.now())

    def __repr__(self):
        return '<Log %r>' % self.id
