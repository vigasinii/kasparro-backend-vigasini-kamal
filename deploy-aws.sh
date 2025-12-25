#!/bin/bash

# Kasparro ETL System - AWS Deployment Script
# This script automates the deployment to AWS

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Kasparro ETL System - AWS Deployment"
echo "=========================================="
echo ""

# Configuration
read -p "Enter your AWS region (default: us-east-1): " AWS_REGION
AWS_REGION=${AWS_REGION:-us-east-1}

read -p "Enter your AWS account ID: " AWS_ACCOUNT_ID
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}AWS Account ID is required${NC}"
    exit 1
fi

read -p "Enter your RDS master password: " -s RDS_PASSWORD
echo ""
if [ -z "$RDS_PASSWORD" ]; then
    echo -e "${RED}RDS password is required${NC}"
    exit 1
fi

read -p "Enter your CoinPaprika API key: " COINPAPRIKA_KEY
if [ -z "$COINPAPRIKA_KEY" ]; then
    echo -e "${RED}CoinPaprika API key is required${NC}"
    exit 1
fi

read -p "Enter your CoinGecko API key (optional): " COINGECKO_KEY

PROJECT_NAME="kasparro"
ECR_REPO="${PROJECT_NAME}-etl"
CLUSTER_NAME="${PROJECT_NAME}-cluster"
SERVICE_NAME="${PROJECT_NAME}-service"
DB_NAME="${PROJECT_NAME}-db"

echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Region: $AWS_REGION"
echo "  Account: $AWS_ACCOUNT_ID"
echo "  ECR Repo: $ECR_REPO"
echo ""
read -p "Continue with deployment? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo -e "${GREEN}Step 1: Checking AWS CLI...${NC}"
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ AWS CLI found${NC}"

echo ""
echo -e "${GREEN}Step 2: Creating ECR repository...${NC}"
aws ecr create-repository \
    --repository-name $ECR_REPO \
    --image-scanning-configuration scanOnPush=true \
    --region $AWS_REGION 2>/dev/null || echo "Repository already exists"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
echo -e "${GREEN}✓ ECR repository ready: $ECR_URI${NC}"

echo ""
echo -e "${GREEN}Step 3: Building and pushing Docker image...${NC}"
echo "Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_URI

echo "Building Docker image..."
docker build -t ${ECR_REPO}:latest .

echo "Tagging image..."
docker tag ${ECR_REPO}:latest ${ECR_URI}:latest

echo "Pushing to ECR..."
docker push ${ECR_URI}:latest

echo -e "${GREEN}✓ Image pushed to ECR${NC}"

echo ""
echo -e "${GREEN}Step 4: Creating VPC and networking...${NC}"

# Create VPC
VPC_ID=$(aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=${PROJECT_NAME}-vpc}]" \
    --query 'Vpc.VpcId' \
    --output text 2>/dev/null || \
    aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=${PROJECT_NAME}-vpc" \
        --query 'Vpcs[0].VpcId' \
        --output text)

echo "VPC ID: $VPC_ID"

# Enable DNS
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support

# Create Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=${PROJECT_NAME}-igw}]" \
    --query 'InternetGateway.InternetGatewayId' \
    --output text 2>/dev/null || \
    aws ec2 describe-internet-gateways \
        --filters "Name=tag:Name,Values=${PROJECT_NAME}-igw" \
        --query 'InternetGateways[0].InternetGatewayId' \
        --output text)

echo "Internet Gateway ID: $IGW_ID"

# Attach IGW to VPC
aws ec2 attach-internet-gateway \
    --internet-gateway-id $IGW_ID \
    --vpc-id $VPC_ID 2>/dev/null || true

# Create subnets
SUBNET1_ID=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.1.0/24 \
    --availability-zone ${AWS_REGION}a \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-subnet-1}]" \
    --query 'Subnet.SubnetId' \
    --output text 2>/dev/null || \
    aws ec2 describe-subnets \
        --filters "Name=tag:Name,Values=${PROJECT_NAME}-subnet-1" \
        --query 'Subnets[0].SubnetId' \
        --output text)

SUBNET2_ID=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.2.0/24 \
    --availability-zone ${AWS_REGION}b \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-subnet-2}]" \
    --query 'Subnet.SubnetId' \
    --output text 2>/dev/null || \
    aws ec2 describe-subnets \
        --filters "Name=tag:Name,Values=${PROJECT_NAME}-subnet-2" \
        --query 'Subnets[0].SubnetId' \
        --output text)

echo "Subnet 1: $SUBNET1_ID"
echo "Subnet 2: $SUBNET2_ID"

# Enable auto-assign public IP
aws ec2 modify-subnet-attribute --subnet-id $SUBNET1_ID --map-public-ip-on-launch
aws ec2 modify-subnet-attribute --subnet-id $SUBNET2_ID --map-public-ip-on-launch

# Create route table
RTB_ID=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT_NAME}-rtb}]" \
    --query 'RouteTable.RouteTableId' \
    --output text 2>/dev/null || \
    aws ec2 describe-route-tables \
        --filters "Name=tag:Name,Values=${PROJECT_NAME}-rtb" \
        --query 'RouteTables[0].RouteTableId' \
        --output text)

# Add route to IGW
aws ec2 create-route \
    --route-table-id $RTB_ID \
    --destination-cidr-block 0.0.0.0/0 \
    --gateway-id $IGW_ID 2>/dev/null || true

# Associate subnets with route table
aws ec2 associate-route-table --subnet-id $SUBNET1_ID --route-table-id $RTB_ID 2>/dev/null || true
aws ec2 associate-route-table --subnet-id $SUBNET2_ID --route-table-id $RTB_ID 2>/dev/null || true

echo -e "${GREEN}✓ VPC and networking configured${NC}"

echo ""
echo -e "${GREEN}Step 5: Storing secrets in AWS Secrets Manager...${NC}"

aws secretsmanager create-secret \
    --name ${PROJECT_NAME}/coinpaprika-key \
    --secret-string "$COINPAPRIKA_KEY" \
    --region $AWS_REGION 2>/dev/null || \
aws secretsmanager update-secret \
    --secret-id ${PROJECT_NAME}/coinpaprika-key \
    --secret-string "$COINPAPRIKA_KEY" \
    --region $AWS_REGION

if [ ! -z "$COINGECKO_KEY" ]; then
    aws secretsmanager create-secret \
        --name ${PROJECT_NAME}/coingecko-key \
        --secret-string "$COINGECKO_KEY" \
        --region $AWS_REGION 2>/dev/null || \
    aws secretsmanager update-secret \
        --secret-id ${PROJECT_NAME}/coingecko-key \
        --secret-string "$COINGECKO_KEY" \
        --region $AWS_REGION
fi

echo -e "${GREEN}✓ API keys stored in Secrets Manager${NC}"

echo ""
echo -e "${GREEN}Step 6: Creating RDS database...${NC}"

# Create DB subnet group
aws rds create-db-subnet-group \
    --db-subnet-group-name ${PROJECT_NAME}-db-subnet \
    --db-subnet-group-description "Subnet group for ${PROJECT_NAME} RDS" \
    --subnet-ids $SUBNET1_ID $SUBNET2_ID \
    --region $AWS_REGION 2>/dev/null || echo "DB subnet group already exists"

# Create security group for RDS
DB_SG_ID=$(aws ec2 create-security-group \
    --group-name ${PROJECT_NAME}-db-sg \
    --description "Security group for ${PROJECT_NAME} RDS" \
    --vpc-id $VPC_ID \
    --query 'GroupId' \
    --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT_NAME}-db-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

# Allow PostgreSQL from VPC
aws ec2 authorize-security-group-ingress \
    --group-id $DB_SG_ID \
    --protocol tcp \
    --port 5432 \
    --cidr 10.0.0.0/16 2>/dev/null || true

# Create RDS instance
echo "Creating RDS instance (this takes ~10 minutes)..."
aws rds create-db-instance \
    --db-instance-identifier $DB_NAME \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 15.3 \
    --master-username kasparro \
    --master-user-password "$RDS_PASSWORD" \
    --allocated-storage 20 \
    --vpc-security-group-ids $DB_SG_ID \
    --db-subnet-group-name ${PROJECT_NAME}-db-subnet \
    --backup-retention-period 7 \
    --publicly-accessible \
    --region $AWS_REGION 2>/dev/null || echo "RDS instance already exists"

echo "Waiting for RDS to be available..."
aws rds wait db-instance-available \
    --db-instance-identifier $DB_NAME \
    --region $AWS_REGION

RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier $DB_NAME \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text \
    --region $AWS_REGION)

echo "RDS Endpoint: $RDS_ENDPOINT"
echo -e "${GREEN}✓ RDS database created${NC}"

echo ""
echo -e "${GREEN}Step 7: Creating ECS cluster...${NC}"

aws ecs create-cluster \
    --cluster-name $CLUSTER_NAME \
    --region $AWS_REGION 2>/dev/null || echo "Cluster already exists"

echo -e "${GREEN}✓ ECS cluster created${NC}"

echo ""
echo -e "${GREEN}Step 8: Creating IAM roles...${NC}"

# Create task execution role
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file://trust-policy.json 2>/dev/null || true

aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true

# Add Secrets Manager access
cat > secrets-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:${PROJECT_NAME}/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-name SecretsManagerAccess \
    --policy-document file://secrets-policy.json 2>/dev/null || true

rm trust-policy.json secrets-policy.json

echo -e "${GREEN}✓ IAM roles configured${NC}"

echo ""
echo -e "${GREEN}Step 9: Creating CloudWatch log group...${NC}"

aws logs create-log-group \
    --log-group-name /ecs/${PROJECT_NAME}-etl \
    --region $AWS_REGION 2>/dev/null || echo "Log group already exists"

aws logs put-retention-policy \
    --log-group-name /ecs/${PROJECT_NAME}-etl \
    --retention-in-days 30 \
    --region $AWS_REGION 2>/dev/null || true

echo -e "${GREEN}✓ CloudWatch log group created${NC}"

echo ""
echo -e "${GREEN}Step 10: Creating ECS task definition...${NC}"

DATABASE_URL="postgresql://kasparro:${RDS_PASSWORD}@${RDS_ENDPOINT}:5432/kasparro_db"

cat > task-definition.json <<EOF
{
  "family": "${PROJECT_NAME}-etl",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "${PROJECT_NAME}-api",
      "image": "${ECR_URI}:latest",
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
          "value": "${DATABASE_URL}"
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
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:${PROJECT_NAME}/coinpaprika-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${PROJECT_NAME}-etl",
          "awslogs-region": "${AWS_REGION}",
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
EOF

aws ecs register-task-definition \
    --cli-input-json file://task-definition.json \
    --region $AWS_REGION

rm task-definition.json

echo -e "${GREEN}✓ Task definition registered${NC}"

echo ""
echo -e "${GREEN}Step 11: Creating Application Load Balancer...${NC}"

# Create ALB security group
ALB_SG_ID=$(aws ec2 create-security-group \
    --group-name ${PROJECT_NAME}-alb-sg \
    --description "Security group for ${PROJECT_NAME} ALB" \
    --vpc-id $VPC_ID \
    --query 'GroupId' \
    --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT_NAME}-alb-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

# Allow HTTP from anywhere
aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 2>/dev/null || true

# Create ALB
ALB_ARN=$(aws elbv2 create-load-balancer \
    --name ${PROJECT_NAME}-alb \
    --subnets $SUBNET1_ID $SUBNET2_ID \
    --security-groups $ALB_SG_ID \
    --scheme internet-facing \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text 2>/dev/null || \
    aws elbv2 describe-load-balancers \
        --names ${PROJECT_NAME}-alb \
        --query 'LoadBalancers[0].LoadBalancerArn' \
        --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns $ALB_ARN \
    --query 'LoadBalancers[0].DNSName' \
    --output text)

# Create target group
TG_ARN=$(aws elbv2 create-target-group \
    --name ${PROJECT_NAME}-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id $VPC_ID \
    --health-check-path /health \
    --target-type ip \
    --region $AWS_REGION \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text 2>/dev/null || \
    aws elbv2 describe-target-groups \
        --names ${PROJECT_NAME}-tg \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text)

# Create listener
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN \
    --region $AWS_REGION 2>/dev/null || echo "Listener already exists"

echo "ALB DNS: $ALB_DNS"
echo -e "${GREEN}✓ Load Balancer created${NC}"

echo ""
echo -e "${GREEN}Step 12: Creating ECS service...${NC}"

# Create ECS security group
ECS_SG_ID=$(aws ec2 create-security-group \
    --group-name ${PROJECT_NAME}-ecs-sg \
    --description "Security group for ${PROJECT_NAME} ECS tasks" \
    --vpc-id $VPC_ID \
    --query 'GroupId' \
    --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${PROJECT_NAME}-ecs-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

# Allow traffic from ALB
aws ec2 authorize-security-group-ingress \
    --group-id $ECS_SG_ID \
    --protocol tcp \
    --port 8000 \
    --source-group $ALB_SG_ID 2>/dev/null || true

# Create ECS service
aws ecs create-service \
    --cluster $CLUSTER_NAME \
    --service-name $SERVICE_NAME \
    --task-definition ${PROJECT_NAME}-etl \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET1_ID,$SUBNET2_ID],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=${PROJECT_NAME}-api,containerPort=8000" \
    --region $AWS_REGION 2>/dev/null || echo "Service already exists"

echo "Waiting for service to stabilize..."
aws ecs wait services-stable \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $AWS_REGION

echo -e "${GREEN}✓ ECS service created and running${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Your application is now running on AWS!"
echo ""
echo "🌐 API Endpoint: http://$ALB_DNS"
echo ""
echo "Test the deployment:"
echo "  curl http://$ALB_DNS/health"
echo "  curl http://$ALB_DNS/data"
echo ""
echo "📊 View logs in CloudWatch:"
echo "  Log Group: /ecs/${PROJECT_NAME}-etl"
echo ""
echo "💾 Database:"
echo "  Endpoint: $RDS_ENDPOINT"
echo "  Database: kasparro_db"
echo "  Username: kasparro"
echo ""
echo "🔑 API Keys stored in Secrets Manager:"
echo "  - ${PROJECT_NAME}/coinpaprika-key"
if [ ! -z "$COINGECKO_KEY" ]; then
    echo "  - ${PROJECT_NAME}/coingecko-key"
fi
echo ""
echo "⚠️  IMPORTANT: Save these details for your submission!"
echo ""
