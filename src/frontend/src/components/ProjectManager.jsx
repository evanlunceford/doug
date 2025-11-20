import React, { useState, useEffect } from 'react';
import Api from '../utils/Api';
import '../css/components/ProjectManager.css';

export default function ProjectManager() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [editingProject, setEditingProject] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    tech_stack: '',
    weekly_hours: 0
  });

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await Api.get('/projects/');
      if (response.success && response.projects) {
        setProjects(response.projects);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const addProject = async () => {
    if (!formData.title.trim()) {
      setError('Title is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await Api.post('/projects/add', formData);

      if (response.success && response.project) {
        setProjects([...projects, response.project]);
        setFormData({ title: '', description: '', tech_stack: '', weekly_hours: 0 });
        setShowAddForm(false);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateProject = async (originalTitle, column, value) => {
    setLoading(true);
    setError(null);

    try {
      const response = await Api.patch('/projects/update', {
        title: originalTitle,
        column,
        value
      });

      if (response.success && response.project) {
        setProjects(projects.map(p => 
          p.title === originalTitle ? response.project : p
        ));
        setEditingProject(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const deleteProject = async (title) => {
    if (!confirm(`Are you sure you want to delete "${title}"?`)) return;

    setLoading(true);
    setError(null);

    try {
      const response = await Api.delete(`/projects/delete-project/${encodeURIComponent(title)}`);

      if (response.success) {
        setProjects(projects.filter(p => p.title !== title));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (project) => {
    setEditingProject({ ...project, originalTitle: project.title });
  };

  const saveEdit = () => {
    const original = editingProject.originalTitle;
    const updates = [];

    if (editingProject.title !== original) {
      updates.push({ column: 'title', value: editingProject.title });
    }
    if (editingProject.description !== projects.find(p => p.title === original)?.description) {
      updates.push({ column: 'description', value: editingProject.description });
    }
    if (editingProject.tech_stack !== projects.find(p => p.title === original)?.tech_stack) {
      updates.push({ column: 'tech_stack', value: editingProject.tech_stack });
    }
    if (editingProject.weekly_hours !== projects.find(p => p.title === original)?.weekly_hours) {
      updates.push({ column: 'weekly_hours', value: parseInt(editingProject.weekly_hours) });
    }

    if (updates.length > 0) {
      let currentTitle = original;
      const updateSequentially = async () => {
        for (const update of updates) {
          await updateProject(currentTitle, update.column, update.value);
          if (update.column === 'title') {
            currentTitle = update.value;
          }
        }
      };
      updateSequentially();
    } else {
      setEditingProject(null);
    }
  };

  return (
    <div className="project-manager">
      <div className="project-container">
        {/* Header */}
        <div className="project-header">
          <h1 className="project-title">Project Manager</h1>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            disabled={loading}
            className="btn-primary"
          >
            Add Project
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {/* Add Form */}
        {showAddForm && (
          <div className="add-form">
            <h2 className="form-title">New Project</h2>
            <div className="form-grid">
              <input
                type="text"
                placeholder="Project Title*"
                value={formData.title}
                onChange={e => setFormData({ ...formData, title: e.target.value })}
                className="form-input"
              />
              <textarea
                placeholder="Description"
                value={formData.description}
                onChange={e => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                className="form-textarea"
              />
              <input
                type="text"
                placeholder="Tech Stack (e.g., React, Python, PostgreSQL)"
                value={formData.tech_stack}
                onChange={e => setFormData({ ...formData, tech_stack: e.target.value })}
                className="form-input"
              />
              <input
                type="number"
                placeholder="Weekly Hours"
                value={formData.weekly_hours}
                onChange={e => setFormData({ ...formData, weekly_hours: parseInt(e.target.value) || 0 })}
                min={0}
                className="form-input"
              />
              <div className="form-actions">
                <button
                  onClick={() => {
                    setShowAddForm(false);
                    setFormData({ title: '', description: '', tech_stack: '', weekly_hours: 0 });
                    setError(null);
                  }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={addProject}
                  disabled={loading}
                  className="btn-primary"
                >
                  {loading ? 'Adding...' : 'Add Project'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Projects List */}
        <div className="projects-list">
          {projects.length === 0 ? (
            <div className="empty-state">
              No projects yet. Click "Add Project" to get started!
            </div>
          ) : (
            projects.map((project) => (
              <div
                key={project.title}
                className={`project-card ${editingProject?.originalTitle === project.title ? 'editing' : ''}`}
              >
                {editingProject?.originalTitle === project.title ? (
                  <div className="form-grid">
                    <input
                      type="text"
                      value={editingProject.title}
                      onChange={e => setEditingProject({ ...editingProject, title: e.target.value })}
                      className="form-input project-title-input"
                    />
                    <textarea
                      value={editingProject.description}
                      onChange={e => setEditingProject({ ...editingProject, description: e.target.value })}
                      rows={3}
                      className="form-textarea"
                    />
                    <input
                      type="text"
                      value={editingProject.tech_stack}
                      onChange={e => setEditingProject({ ...editingProject, tech_stack: e.target.value })}
                      className="form-input"
                    />
                    <input
                      type="number"
                      value={editingProject.weekly_hours}
                      onChange={e => setEditingProject({ ...editingProject, weekly_hours: parseInt(e.target.value) || 0 })}
                      min={0}
                      className="form-input"
                    />
                    <div className="form-actions">
                      <button
                        onClick={() => setEditingProject(null)}
                        className="btn-icon-secondary"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={saveEdit}
                        disabled={loading}
                        className="btn-icon-primary"
                      >
                        {loading ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="project-card-header">
                      <h3 className="project-card-title">{project.title}</h3>
                      <div className="project-actions">
                        <button
                          onClick={() => startEdit(project)}
                          disabled={loading}
                          className="btn-icon"
                        >
                        </button>
                        <button
                          onClick={() => deleteProject(project.title)}
                          disabled={loading}
                          className="btn-icon btn-icon-delete"
                        >
                        </button>
                      </div>
                    </div>
                    {project.description && (
                      <p className="project-description">{project.description}</p>
                    )}
                    <div className="project-meta">
                      {project.tech_stack && (
                        <div className="project-badge">
                          🛠️ {project.tech_stack}
                        </div>
                      )}
                      <div className="project-badge project-badge-hours">
                        ⏱️ {project.weekly_hours}h/week
                      </div>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}