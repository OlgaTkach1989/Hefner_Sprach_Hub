FROM quay.io/jupyterhub/singleuser:5.4

LABEL org.opencontainers.image.authors="Serhii TK" \
      org.opencontainers.image.vendor="Serhii TK" \
      org.opencontainers.image.title="Learning Hub Jupyter Runtime" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g configurable-http-proxy \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    jupyterlab==4.4.9 \
    notebook==7.4.7 \
    jupyter_ai==2.31.7 \
    langchain-openai==0.3.35 \
    numpy==2.3.3 \
    pandas==2.3.2 \
    matplotlib==3.10.6 \
    requests==2.32.5 \
    ipywidgets==8.1.7 \
    nbgrader==0.9.5 \
    otter-grader==6.1.4 \
    docker==7.1.0 \
    dockerspawner==14.0.0

COPY hub/jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
COPY hub/external_token_auth.py /srv/jupyterhub/external_token_auth.py
COPY hub/learning_hub_singleuser_start.sh /usr/local/bin/learning-hub-singleuser-start.sh
COPY hub/00-fix-jupyterhub-data-perms.sh /usr/local/bin/start-notebook.d/00-fix-jupyterhub-data-perms.sh
COPY hub/10-load-jupyter-ai.py /home/jovyan/.ipython/profile_default/startup/10-load-jupyter-ai.py
COPY hub/ipython_config.py /home/jovyan/.ipython/profile_default/ipython_config.py
COPY hub/jupyter_server_config.py /home/jovyan/.jupyter/jupyter_server_config.py
COPY content /opt/training-content

RUN chmod 0755 /usr/local/bin/learning-hub-singleuser-start.sh \
    && chmod 0755 /usr/local/bin/start-notebook.d/00-fix-jupyterhub-data-perms.sh \
    && mkdir -p /data /opt/training-content /home/jovyan/work /home/jovyan/.jupyter /home/jovyan/.ipython/profile_default/startup \
    && chown -R ${NB_UID}:${NB_GID} /home/jovyan /opt/training-content \
    && chmod -R 0755 /opt/training-content

USER ${NB_UID}

EXPOSE 8000

CMD ["jupyterhub", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
