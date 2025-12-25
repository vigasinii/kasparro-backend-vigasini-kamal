# AWS Deployment - Quick Start Guide

Deploy your Kasparro ETL system to AWS in under 20 minutes!

## Prerequisites

Before you start, make sure you have:

1. **AWS Account** - [Sign up here](https://aws.amazon.com/) if you don't have one
2. **AWS CLI installed** - [Installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
3. **Docker installed** - Should already be installed from local setup
4. **API Keys**:
   - CoinPaprika API key ([Get here](https://coinpaprika.com/api))
   - CoinGecko API key (optional) ([Get here](https://www.coingecko.com/en/api))

## Option 1: Automated Deployment (Recommended)

### Step 1: Configure AWS CLI

```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Default output format: `json`

**Don't have AWS credentials?**
1. Go to AWS Console → IAM → Users → Your User
2. Security credentials → Create access key
3. Choose "Command Line Interface (CLI)"
4. Download the credentials

### Step 2: Run Deployment Script

```bash
cd kasparro-backend-vic
./deploy-aws.sh
```

The script will prompt you for:
- AWS region (default: us-east-1)
- AWS account ID (find in AWS Console, top-right)
- RDS password (create a secure password)
- CoinPaprika API key
- CoinGecko API key (optional)

**That's it!** The script will:
- ✅ Create all AWS resources
- ✅ Build and push Docker image
- ✅ Set up database
- ✅ Deploy ECS service
- ✅ Configure load balancer

**Deployment takes ~15 minutes** (RDS creation is the longest part)

### Step 3: Test Your Deployment

Once complete, the script will show you the API endpoint:

```bash
# Test health
curl http://your-alb-dns/health

# Test data endpoint
curl http://your-alb-dns/data

# View in browser
open http://your-alb-dns/docs
```

## Option 2: Manual AWS Console Deployment

If you prefer clicking buttons, follow the detailed guide in `DEPLOYMENT.md`.

## What Gets Created

The deployment script creates:

1. **Networking**:
   - VPC with 2 subnets (Multi-AZ)
   - Internet Gateway
   - Route tables
   - Security groups

2. **Database**:
   - RDS PostgreSQL (db.t3.micro)
   - Automated backups
   - Multi-AZ for high availability

3. **Container Service**:
   - ECR repository for Docker images
   - ECS Fargate cluster
   - ECS service with 1 task

4. **Load Balancing**:
   - Application Load Balancer
   - Target group
   - Health checks

5. **Secrets**:
   - API keys in Secrets Manager
   - Secure credential storage

6. **Monitoring**:
   - CloudWatch log group
   - Log retention (30 days)

## Estimated Monthly Cost

- **ECS Fargate** (1 task): ~$15
- **RDS db.t3.micro**: ~$15
- **Application Load Balancer**: ~$20
- **Data Transfer**: ~$5
- **CloudWatch Logs**: ~$5
- **NAT Gateway** (if needed): ~$30

**Total: ~$60-90/month**

You can use **AWS Free Tier** for the first 12 months to reduce costs!

## After Deployment

### Verify Everything Works

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster kasparro-cluster \
  --services kasparro-service

# View logs
aws logs tail /ecs/kasparro-etl --follow

# Check database connectivity
aws rds describe-db-instances \
  --db-instance-identifier kasparro-db
```

### Access Your Application

Your app is now live at: `http://your-alb-dns`

**Available endpoints**:
- `/` - API info
- `/health` - Health check
- `/data` - Cryptocurrency data
- `/stats` - ETL statistics
- `/docs` - Interactive API documentation
- `/metrics` - Prometheus metrics

### Run Database Migrations

If this is the first deployment:

```bash
# Get task ID
TASK_ID=$(aws ecs list-tasks \
  --cluster kasparro-cluster \
  --service-name kasparro-service \
  --query 'taskArns[0]' \
  --output text | rev | cut -d'/' -f1 | rev)

# Connect to task
aws ecs execute-command \
  --cluster kasparro-cluster \
  --task $TASK_ID \
  --container kasparro-api \
  --interactive \
  --command "/bin/bash"

# Inside container, run migrations
alembic upgrade head
exit
```

## Setting Up Scheduled ETL (Optional)

The ETL runs automatically every 6 hours inside the container. If you want external scheduling:

### Create EventBridge Rule

```bash
# Create rule
aws events put-rule \
  --name kasparro-etl-schedule \
  --schedule-expression "rate(6 hours)" \
  --state ENABLED

# Add ECS task as target (see DEPLOYMENT.md for full command)
```

## Monitoring Your Deployment

### View Logs

**AWS Console**:
1. Go to CloudWatch → Log groups
2. Select `/ecs/kasparro-etl`
3. View log streams

**CLI**:
```bash
aws logs tail /ecs/kasparro-etl --follow
```

### Check Metrics

Visit your API: `http://your-alb-dns/stats`

```json
[
  {
    "source": "coinpaprika",
    "records_processed": 50,
    "last_success": "2024-01-15T10:30:00Z",
    "success_rate": 100.0
  }
]
```

### Health Dashboard

Visit: `http://your-alb-dns/health`

```json
{
  "status": "healthy",
  "database": "connected",
  "etl_status": {
    "coinpaprika": {
      "last_run_status": "success",
      "records_processed": 50
    }
  }
}
```

## Troubleshooting

### Task fails to start

**Check logs**:
```bash
aws logs tail /ecs/kasparro-etl --follow
```

**Common issues**:
- Database not ready: Wait 1-2 more minutes
- API keys missing: Check Secrets Manager
- Health check failing: Increase `startPeriod` in task definition

### Can't access API

**Check security groups**:
```bash
# Verify ALB security group allows port 80
aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=kasparro-alb-sg"
```

**Check target health**:
```bash
aws elbv2 describe-target-health \
  --target-group-arn <your-tg-arn>
```

### Database connection fails

**Test connectivity**:
```bash
# From your local machine (if RDS is public)
psql -h <rds-endpoint> -U kasparro -d kasparro_db

# Or from ECS task
aws ecs execute-command \
  --cluster kasparro-cluster \
  --task <task-id> \
  --container kasparro-api \
  --interactive \
  --command "/bin/bash"
```

## Updating Your Deployment

When you make code changes:

```bash
# 1. Rebuild and push image
./deploy-aws.sh  # or just the ECR login + push steps

# 2. Force new deployment
aws ecs update-service \
  --cluster kasparro-cluster \
  --service kasparro-service \
  --force-new-deployment
```

## Cleaning Up (Delete Everything)

**WARNING**: This deletes all resources and data!

```bash
# Delete ECS service
aws ecs delete-service \
  --cluster kasparro-cluster \
  --service kasparro-service \
  --force

# Delete ECS cluster
aws ecs delete-cluster --cluster kasparro-cluster

# Delete RDS (creates final snapshot)
aws rds delete-db-instance \
  --db-instance-identifier kasparro-db \
  --final-db-snapshot-identifier kasparro-final-snapshot

# Delete load balancer
aws elbv2 delete-load-balancer --load-balancer-arn <alb-arn>

# Delete target group
aws elbv2 delete-target-group --target-group-arn <tg-arn>

# Delete VPC resources (in order):
# - Security groups
# - Subnets
# - Route tables
# - Internet Gateway
# - VPC

# Or use AWS Console → VPC → Delete VPC (deletes everything)
```

## For Assignment Submission

After deployment, you need to provide:

1. **Public API URL**: `http://your-alb-dns`
2. **Cron/Scheduler**: ETL runs every 6 hours (built-in)
3. **Logs access**: CloudWatch log group `/ecs/kasparro-etl`
4. **Metrics**: Available at `/metrics` and `/stats`

**Demo checklist**:
- ✅ Show `/health` endpoint
- ✅ Show `/data` endpoint with real data
- ✅ Show CloudWatch logs
- ✅ Show `/stats` with ETL metrics
- ✅ Explain the architecture

## Getting Help

**Common AWS CLI commands**:
```bash
# Check AWS identity
aws sts get-caller-identity

# List ECS tasks
aws ecs list-tasks --cluster kasparro-cluster

# Describe task
aws ecs describe-tasks \
  --cluster kasparro-cluster \
  --tasks <task-id>

# View CloudWatch logs
aws logs tail /ecs/kasparro-etl --follow --since 10m
```

**Need more help?**
- AWS Documentation: https://docs.aws.amazon.com/
- Join Kasparro Discord for questions
- Check `DEPLOYMENT.md` for detailed steps

## What's Next?

Once deployed:
1. ✅ Verify all endpoints work
2. ✅ Check CloudWatch logs
3. ✅ Monitor ETL runs in `/stats`
4. ✅ Test the `/docs` page
5. ✅ Prepare your demo

**You're ready for the assignment submission!** 🚀

---

**Pro tip**: Take screenshots of your CloudWatch logs and API responses for your demo!
