import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean, LargeBinary
from sqlalchemy.orm import relationship
from .database import Base

def uid(): return uuid.uuid4().hex

def now(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id = Column(String(32), primary_key=True, default=uid)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(200), nullable=False, default='Administrador')
    password_hash = Column(String(300), nullable=False)
    role = Column(String(30), default='admin')
    created_at = Column(DateTime(timezone=True), default=now)

class Project(Base):
    __tablename__ = 'projects'
    id = Column(String(32), primary_key=True, default=uid)
    name = Column(String(250), nullable=False)
    description = Column(Text, default='')
    created_at = Column(DateTime(timezone=True), default=now)

class Person(Base):
    __tablename__ = 'people'
    id = Column(String(32), primary_key=True, default=uid)
    name = Column(String(200), nullable=False)
    kind = Column(String(20), default='person')
    role = Column(String(150), default='')
    notes = Column(Text, default='')

class Activity(Base):
    __tablename__ = 'activities'
    id = Column(String(32), primary_key=True, default=uid)
    project_id = Column(String(32), ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    title = Column(String(300), default='Nova evidência', nullable=False)
    description = Column(Text, default='')
    activity_date = Column(String(10), default='')
    location = Column(String(300), default='')
    participants = Column(Text, default='')
    objective = Column(Text, default='')
    results = Column(Text, default='')
    indicators = Column(Text, default='')
    competencies = Column(Text, default='')
    conclusions = Column(Text, default='')
    status = Column(String(20), default='draft')
    created_by = Column(String(32), ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)
    groups = relationship('PhotoGroup', order_by='PhotoGroup.position', cascade='all, delete-orphan', back_populates='activity')
    documents = relationship('GeneratedDocument', cascade='all, delete-orphan')
    project = relationship('Project')

class PhotoGroup(Base):
    __tablename__ = 'photo_groups'
    id = Column(String(32), primary_key=True, default=uid)
    activity_id = Column(String(32), ForeignKey('activities.id', ondelete='CASCADE'), nullable=False)
    position = Column(Integer, nullable=False)
    title = Column(String(250), default='')
    description = Column(Text, default='')
    people = Column(Text, default='')
    activity = relationship('Activity', back_populates='groups')
    photos = relationship('Photo', order_by='Photo.position', cascade='all, delete-orphan', back_populates='group')

class Photo(Base):
    __tablename__ = 'photos'
    id = Column(String(32), primary_key=True, default=uid)
    group_id = Column(String(32), ForeignKey('photo_groups.id', ondelete='CASCADE'), nullable=False)
    filename = Column(String(300), nullable=False)
    original_name = Column(String(250), default='')
    description = Column(Text, default='')
    people = Column(Text, default='')
    position = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now)
    blob = Column(LargeBinary, nullable=True)
    group = relationship('PhotoGroup', back_populates='photos')

class KnowledgeDocument(Base):
    __tablename__ = 'knowledge_documents'
    id = Column(String(32), primary_key=True, default=uid)
    title = Column(String(250), nullable=False)
    source = Column(String(300), default='')
    content = Column(Text, nullable=False)
    verified = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)
    chunks = relationship('KnowledgeChunk', cascade='all, delete-orphan')

class KnowledgeChunk(Base):
    __tablename__ = 'knowledge_chunks'
    id = Column(String(32), primary_key=True, default=uid)
    document_id = Column(String(32), ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=False)
    position = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    document = relationship('KnowledgeDocument', overlaps='chunks')

class DocumentTemplate(Base):
    __tablename__ = 'document_templates'
    id = Column(String(32), primary_key=True, default=uid)
    name = Column(String(200), nullable=False)
    layout = Column(String(30), nullable=False, default='institutional')
    subtitle = Column(String(200), default='RELATÓRIO DE EVIDÊNCIA')
    institution = Column(String(250), default='')
    color = Column(String(7), default='#125e78')
    footer = Column(String(300), default='Documento de evidência institucional')
    created_at = Column(DateTime(timezone=True), default=now)

class GeneratedDocument(Base):
    __tablename__ = 'generated_documents'
    id = Column(String(32), primary_key=True, default=uid)
    activity_id = Column(String(32), ForeignKey('activities.id', ondelete='CASCADE'), nullable=False)
    template_id = Column(String(32), ForeignKey('document_templates.id', ondelete='SET NULL'), nullable=True)
    filename = Column(String(300), nullable=False)
    format = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), default=now)
    created_by = Column(String(32), ForeignKey('users.id'), nullable=True)
    blob = Column(LargeBinary, nullable=True)

class AppSetting(Base):
    __tablename__ = 'app_settings'
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(String(32), primary_key=True, default=uid)
    activity_id = Column(String(32), ForeignKey('activities.id', ondelete='CASCADE'), nullable=True)
    user_id = Column(String(32), ForeignKey('users.id'), nullable=True)
    action = Column(String(100), nullable=False)
    detail = Column(Text, default='')
    timestamp = Column(DateTime(timezone=True), default=now)


class AppSession(Base):
    __tablename__ = 'app_sessions'
    id = Column(String(64), primary_key=True)
    user_id = Column(String(32), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
