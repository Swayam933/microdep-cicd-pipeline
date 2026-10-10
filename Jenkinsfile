def SERVICES = ['orders-service', 'inventory-service']
def deploymentsToRollback = []

pipeline {
    agent any

    parameters {
        string(
            name: 'IMAGE_REGISTRY',
            defaultValue: '',
            description: 'GHCR image prefix, for example ghcr.io/my-user/microdep'
        )
    }

    environment {
        KUBECONFIG = credentials('kubeconfig-microdep')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Validate image registry') {
            steps {
                script {
                    if (!(params.IMAGE_REGISTRY ==~ /ghcr\.io\/[a-z0-9_.-]+\/[a-z0-9_.-]+/)) {
                        error('IMAGE_REGISTRY must be ghcr.io/<owner>/<package>.')
                    }
                }
            }
        }

        stage('Build & Unit Test') {
            steps {
                script {
                    for (svc in SERVICES) {
                        dir("services/${svc}") {
                            sh '''
                                python3 -m venv .venv
                                . .venv/bin/activate
                                pip install --disable-pip-version-check -r requirements.txt pytest
                                pytest --junitxml=test-results.xml
                            '''
                        }
                    }
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'services/*/test-results.xml'
                }
            }
        }

        stage('Build & Push Images') {
            steps {
                script {
                    withCredentials([usernamePassword(
                        credentialsId: 'registry-credentials',
                        usernameVariable: 'REGISTRY_USER',
                        passwordVariable: 'REGISTRY_PASSWORD'
                    )]) {
                        sh '''
                            printf '%s' "$REGISTRY_PASSWORD" |
                              docker login ghcr.io --username "$REGISTRY_USER" --password-stdin
                        '''
                        try {
                            for (svc in SERVICES) {
                                def image = "${params.IMAGE_REGISTRY}/${svc}:${env.GIT_COMMIT}"
                                withEnv(["IMAGE_NAME=${image}"]) {
                                    withEnv(["SERVICE_PATH=services/${svc}"]) {
                                        sh 'docker build --tag "$IMAGE_NAME" "$SERVICE_PATH"'
                                    }
                                    sh 'docker push "$IMAGE_NAME"'
                                }
                            }
                        } finally {
                            sh 'docker logout ghcr.io'
                        }
                    }
                }
            }
        }

        stage('Deploy to Kubernetes (EKS)') {
            steps {
                script {
                    sh 'kubectl apply -f k8s/namespace-and-ingress.yaml'
                    for (svc in SERVICES) {
                        def exists = sh(
                            returnStatus: true,
                            script: "kubectl get deployment ${svc} --namespace=microdep"
                        ) == 0
                        def previousImage = exists ? sh(
                            returnStdout: true,
                            script: "kubectl get deployment ${svc} --namespace=microdep -o jsonpath='{.spec.template.spec.containers[0].image}'"
                        ).trim() : ''
                        def image = "${params.IMAGE_REGISTRY}/${svc}:${env.GIT_COMMIT}"

                        withEnv([
                            "IMAGE_NAME=${image}",
                            "SERVICE_NAME=${svc}"
                        ]) {
                            sh '''
                                sed -e "s|ghcr.io/OWNER/REPO/${SERVICE_NAME}:REPLACE_ME|${IMAGE_NAME}|g" \
                                  -e "s|value: \"dev\"|value: \"${GIT_COMMIT}\"|g" \
                                  "k8s/${SERVICE_NAME}.yaml" | kubectl apply -f -
                            '''
                        }
                        if (exists && previousImage != image) {
                            deploymentsToRollback.add(svc)
                        }
                        sh "kubectl rollout status deployment/${svc} --namespace=microdep --timeout=180s"
                    }
                }
            }
        }

        stage('Post-Deploy Smoke Test') {
            steps {
                sh '''
                    set -eu
                    kubectl port-forward --namespace=microdep svc/orders-service 18080:80 \
                      > orders-port-forward.log 2>&1 &
                    orders_pid=$!
                    kubectl port-forward --namespace=microdep svc/inventory-service 18081:80 \
                      > inventory-port-forward.log 2>&1 &
                    inventory_pid=$!
                    cleanup() {
                      kill "$orders_pid" "$inventory_pid" 2>/dev/null || true
                      rm -f orders-port-forward.log inventory-port-forward.log
                    }
                    trap cleanup EXIT

                    ready=false
                    for attempt in $(seq 1 30); do
                      if curl --fail --silent http://127.0.0.1:18080/healthz >/dev/null &&
                         curl --fail --silent http://127.0.0.1:18081/healthz >/dev/null; then
                        ready=true
                        break
                      fi
                      sleep 1
                    done
                    if [ "$ready" != true ]; then
                      echo "Service port-forwards did not become ready." >&2
                      cat orders-port-forward.log inventory-port-forward.log >&2
                      exit 1
                    fi
                    curl --fail --silent http://127.0.0.1:18080/metrics >/dev/null
                    curl --fail --silent http://127.0.0.1:18081/metrics >/dev/null
                '''
            }
        }
    }

    post {
        failure {
            script {
                for (svc in deploymentsToRollback.reverse()) {
                    sh "kubectl rollout undo deployment/${svc} --namespace=microdep"
                    sh "kubectl rollout status deployment/${svc} --namespace=microdep --timeout=180s"
                }
            }
        }
    }
}
