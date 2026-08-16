output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.gpu_bench.id
}

output "public_ip" {
  description = "Public IP of the GPU instance"
  value       = aws_instance.gpu_bench.public_ip
}

output "vllm_endpoint" {
  description = "vLLM API endpoint"
  value       = "http://${aws_instance.gpu_bench.public_ip}:8000"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_instance.gpu_bench.public_ip}"
}
