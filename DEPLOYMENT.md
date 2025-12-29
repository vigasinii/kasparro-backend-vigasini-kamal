# Deployment Guide

## ✅ Live Production Deployment

**AWS URL:** http://kasparro-alb-337095253.us-east-1.elb.amazonaws.com

### Verification Links:
- Health Check: http://kasparro-alb-337095253.us-east-1.elb.amazonaws.com/health
- API Data: http://kasparro-alb-337095253.us-east-1.elb.amazonaws.com/data
- Interactive Docs: http://kasparro-alb-337095253.us-east-1.elb.amazonaws.com/docs

### AWS Resources:
- ECS Cluster: kasparro-cluster
- RDS Database: kasparro-db.c8jy2ocao27x.us-east-1.rds.amazonaws.com
- Load Balancer: kasparro-alb-337095253.us-east-1.elb.amazonaws.com
- ECR Repository: 602644258400.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl

---

# AWS Deployment Guide

This guide walks through deploying the Kasparro ETL system to AWS.

## Architecture Overview

```
                                 ┌─────────────────────┐
                                 │   Route 53 (DNS)    │
                                 └──────────┬──────────┘
                                            │
                                 ┌──────────▼──────────┐
                                 │  Application Load   │
                                 │     Balancer        │
                                 └──────────┬──────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              │                             │                             │
    ┌─────────▼────────┐        ┌─────────▼────────┐        ┌──────────▼────────┐
    │   ECS Task 1     │        │   ECS Task 2     │        │   ECS Task N      │
    │  - API Service   │        │  - API Service   │        │  - API Service    │
    │  - ETL Service   │        │  - ETL Service   │        │  - ETL Service    │
    └──────────────────┘        └──────────────────┘        └───────────────────┘
              │                             │                             │
              └─────────────────────────────┼─────────────────────────────┘
                                            │
                                 ┌──────────▼──────────┐
                                 │   RDS PostgreSQL    │
                                 │   (Multi-AZ)        │
                                 └─────────────────────┘
```

## Prerequisites

1. AWS Account with appropriate permissions
2. AWS CLI installed and configured
3. Docker installed locally
4. API keys for CoinPaprika and CoinGecko

## Step 1: Set Up AWS Resources

### 1.1 Create VPC and Networking

```bash
# Create VPC
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=kasparro-vpc}]'

# Create subnets (2 public, 2 private in different AZs)
aws ec2 create-subnet \
  --vpc-id <vpc-id> \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a

# Create Internet Gateway
aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=kasparro-igw}]'

# Attach to VPC
aws ec2 attach-internet-gateway \
  --internet-gateway-id <igw-id> \
  --vpc-id <vpc-id>
```

### 1.2 Create RDS PostgreSQL Database

```bash
# Create DB subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name kasparro-db-subnet \
  --db-subnet-group-description "Kasparro DB subnet group" \
  --subnet-ids <subnet-id-1> <subnet-id-2>

# Create security group
aws ec2 create-security-group \
  --group-name kasparro-db-sg \
  --description "Security group for Kasparro RDS" \
  --vpc-id <vpc-id>

# Allow inbound PostgreSQL
aws ec2 authorize-security-group-ingress \
  --group-id <sg-id> \
  --protocol tcp \
  --port 5432 \
  --cidr 10.0.0.0/16

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier kasparro-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.3 \
  --master-username kasparro \
  --master-user-password <secure-password> \
  --allocated-storage 20 \
  --vpc-security-group-ids <sg-id> \
  --db-subnet-group-name kasparro-db-subnet \
  --backup-retention-period 7 \
  --multi-az
```

### 1.3 Create ECR Repository

```bash
# Create repository
aws ecr create-repository \
  --repository-name kasparro-etl \
  --image-scanning-configuration scanOnPush=true

# Get login token
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

## Step 2: Build and Push Docker Image

```bash
# Build image
docker build -t kasparro-etl:latest .

# Tag for ECR
docker tag kasparro-etl:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl:latest
```

## Step 3: Create ECS Cluster and Task Definition

### 3.1 Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name kasparro-cluster
```

### 3.2 Create Task Definition

Save as `task-definition.json`:

```json
{
  "family": "kasparro-etl",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "kasparro-api",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://kasparro:<password>@<rds-endpoint>:5432/kasparro_db"
        },
        {
          "name": "API_HOST",
          "value": "0.0.0.0"
        },
        {
          "name": "API_PORT",
          "value": "8000"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "secrets": [
        {
          "name": "COINPAPRIKA_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:kasparro/coinpaprika-key"
        },
        {
          "name": "COINGECKO_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:kasparro/coingecko-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/kasparro-etl",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

Register task definition:

```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

### 3.3 Store Secrets in AWS Secrets Manager

```bash
# Store CoinPaprika API key
aws secretsmanager create-secret \
  --name kasparro/coinpaprika-key \
  --secret-string "<your-api-key>"

# Store CoinGecko API key
aws secretsmanager create-secret \
  --name kasparro/coingecko-key \
  --secret-string "<your-api-key>"
```

## Step 4: Create Application Load Balancer

```bash
# Create security group for ALB
aws ec2 create-security-group \
  --group-name kasparro-alb-sg \
  --description "Security group for Kasparro ALB" \
  --vpc-id <vpc-id>

# Allow HTTP/HTTPS
aws ec2 authorize-security-group-ingress \
  --group-id <alb-sg-id> \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-id <alb-sg-id> \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# Create ALB
aws elbv2 create-load-balancer \
  --name kasparro-alb \
  --subnets <subnet-id-1> <subnet-id-2> \
  --security-groups <alb-sg-id> \
  --scheme internet-facing

# Create target group
aws elbv2 create-target-group \
  --name kasparro-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id <vpc-id> \
  --health-check-path /health \
  --target-type ip

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn <alb-arn> \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=<tg-arn>
```

## Step 5: Create ECS Service

```bash
# Create security group for ECS tasks
aws ec2 create-security-group \
  --group-name kasparro-ecs-sg \
  --description "Security group for Kasparro ECS tasks" \
  --vpc-id <vpc-id>

# Allow traffic from ALB
aws ec2 authorize-security-group-ingress \
  --group-id <ecs-sg-id> \
  --protocol tcp \
  --port 8000 \
  --source-group <alb-sg-id>

# Create ECS service
aws ecs create-service \
  --cluster kasparro-cluster \
  --service-name kasparro-service \
  --task-definition kasparro-etl \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<subnet-id-1>,<subnet-id-2>],securityGroups=[<ecs-sg-id>],assignPublicIp=DISABLED}" \
  --load-balancers targetGroupArn=<tg-arn>,containerName=kasparro-api,containerPort=8000
```

## Step 6: Set Up EventBridge for ETL Scheduling

### Create EventBridge Rule

```bash
# Create IAM role for EventBridge
aws iam create-role \
  --role-name EventBridgeECSRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "events.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach policy
aws iam attach-role-policy \
  --role-name EventBridgeECSRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceEventsRole

# Create EventBridge rule (runs every 6 hours)
aws events put-rule \
  --name kasparro-etl-schedule \
  --schedule-expression "rate(6 hours)" \
  --state ENABLED

# Add ECS task as target
aws events put-targets \
  --rule kasparro-etl-schedule \
  --targets "Id"="1","Arn"="arn:aws:ecs:us-east-1:<account-id>:cluster/kasparro-cluster","RoleArn"="arn:aws:iam::<account-id>:role/EventBridgeECSRole","EcsParameters"="{TaskDefinitionArn=arn:aws:ecs:us-east-1:<account-id>:task-definition/kasparro-etl:1,TaskCount=1,LaunchType=FARGATE,NetworkConfiguration={awsvpcConfiguration={Subnets=[<subnet-id-1>,<subnet-id-2>],SecurityGroups=[<ecs-sg-id>],AssignPublicIp=DISABLED}}}"
```

## Step 7: Set Up CloudWatch Logs

```bash
# Create log group
aws logs create-log-group --log-group-name /ecs/kasparro-etl

# Set retention
aws logs put-retention-policy \
  --log-group-name /ecs/kasparro-etl \
  --retention-in-days 30
```

## Step 8: Run Database Migrations

```bash
# Connect to one of the ECS tasks
aws ecs execute-command \
  --cluster kasparro-cluster \
  --task <task-id> \
  --container kasparro-api \
  --interactive \
  --command "/bin/bash"

# Inside the container
alembic upgrade head
```

## Step 9: Verify Deployment

```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers \
  --names kasparro-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text

# Test endpoints
curl http://<alb-dns-name>/health
curl http://<alb-dns-name>/data
curl http://<alb-dns-name>/stats
```

## Monitoring and Logging

### CloudWatch Dashboards

Create a CloudWatch dashboard to monitor:
- ECS task CPU/Memory utilization
- RDS connections and performance
- ALB request count and latency
- ETL run success/failure rates

### CloudWatch Alarms

```bash
# CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name kasparro-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# Database connections alarm
aws cloudwatch put-metric-alarm \
  --alarm-name kasparro-db-connections \
  --alarm-description "Alert when DB connections are high" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```



## Estimated Monthly Cost

- **ECS Fargate** (2 tasks): ~$30
- **RDS db.t3.micro** (Multi-AZ): ~$30
- **Application Load Balancer**: ~$20
- **Data Transfer**: ~$5
- **CloudWatch Logs**: ~$5
- **Total**: ~$90/month


